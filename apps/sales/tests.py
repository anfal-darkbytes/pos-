import json
import uuid
from decimal import Decimal
from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from apps.core.models import StoreSettings, PaymentAccount
from apps.customers.models import Customer
from apps.inventory.models import Category, Product
from apps.sales.models import Order, OrderItem, OrderPayment


class SalesAndSyncAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.settings = StoreSettings.get_settings()
        self.settings.tax_rate = Decimal("8.00")
        self.settings.currency_symbol = "$"
        self.settings.save()

        self.category = Category.objects.create(name="Beverages", color="#10b981")
        self.product1 = Product.objects.create(
            name="Green Tea Bottle",
            sku="TEA-001",
            barcode="890123456001",
            category=self.category,
            price=Decimal("2.50"),
            cost=Decimal("1.00"),
            stock=20,
            unit="btl",
            is_active=True,
        )
        self.product2 = Product.objects.create(
            name="Sparkling Water",
            sku="WAT-002",
            barcode="890123456002",
            category=self.category,
            price=Decimal("1.50"),
            cost=Decimal("0.50"),
            stock=10,
            unit="can",
            is_active=True,
        )
        self.customer = Customer.objects.create(
            name="Alice Smith",
            email="alice@example.com",
            phone="+1 555 0199",
            loyalty_points=50,
            total_spent=Decimal("100.00"),
            orders_count=4,
        )

    def test_checkout_online_normal(self):
        payload = {
            "items": [
                {"productId": str(self.product1.id), "quantity": 2},
                {"productId": str(self.product2.id), "quantity": 1},
            ],
            "customer_id": str(self.customer.id),
            "payment_method": "cash",
            "tax_rate": 8.0,
            "discount": 0.50,
        }
        res = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("order", data)
        order = data["order"]
        # Subtotal: 2*2.50 + 1*1.50 = 6.50
        self.assertEqual(order["subtotal"], 6.50)
        # Tax: 6.50 * 8% = 0.52
        self.assertEqual(order["tax"], 0.52)
        # Total: 6.50 + 0.52 - 0.50 = 6.52
        self.assertEqual(order["total"], 6.52)

        # Check stock decremented
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 18)
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock, 9)

        # Check customer stats updated
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.orders_count, 5)
        self.assertEqual(float(self.customer.total_spent), 106.52)
        self.assertEqual(self.customer.loyalty_points, 56)

    def test_idempotent_duplicate_checkout(self):
        client_id = f"client-tx-{uuid.uuid4()}"
        payload = {
            "client_id": client_id,
            "items": [{"productId": str(self.product1.id), "quantity": 3}],
            "payment_method": "cash",
        }

        # First request
        res1 = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertFalse(data1.get("idempotent_replay", False))
        order_num = data1["order"]["order_number"]

        # Stock check: 20 - 3 = 17
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 17)

        # Replayed request with SAME client_id
        res2 = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2.get("idempotent_replay", False))
        self.assertEqual(data2["order"]["order_number"], order_num)

        # Critical: stock must NOT be decremented again!
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 17)
        self.assertEqual(Order.objects.filter(client_id=client_id).count(), 1)

    def test_sync_orders_batch(self):
        client_id_1 = f"sync-{uuid.uuid4()}"
        client_id_2 = f"sync-{uuid.uuid4()}"
        temp_cust_id = f"cust-{uuid.uuid4()}"

        batch_payload = {
            "operations": [
                {
                    "id": temp_cust_id,
                    "type": "create_customer",
                    "payload": {
                        "client_id": temp_cust_id,
                        "name": "Bob Miller",
                        "phone": "+1 555 9876",
                        "email": "bob@example.com",
                    },
                },
                {
                    "id": client_id_1,
                    "type": "create_order",
                    "payload": {
                        "client_id": client_id_1,
                        "items": [{"productId": str(self.product1.id), "quantity": 1}],
                        "customer_id": temp_cust_id,
                        "payment_method": "bank",
                    },
                },
                {
                    "id": client_id_2,
                    "type": "create_order",
                    "payload": {
                        "client_id": client_id_2,
                        "items": [{"productId": str(self.product2.id), "quantity": 2}],
                        "payment_method": "wallet",
                    },
                },
            ]
        }

        res = self.client.post("/api/sync/orders", data=json.dumps(batch_payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn(client_id_1, data["synced"])
        self.assertIn(client_id_2, data["synced"])

        # Check orders created with correct customer foreign key
        order1 = Order.objects.get(client_id=client_id_1)
        self.assertIsNotNone(order1.customer)
        self.assertEqual(order1.customer.name, "Bob Miller")
        self.assertTrue(order1.is_offline_sync)

        order2 = Order.objects.get(client_id=client_id_2)
        self.assertEqual(order2.payment_method, "wallet")

    def test_inventory_oversell_conflict_resolution(self):
        # Product2 has stock = 10. Let's simulate terminal A sold 8, terminal B sold 5 offline.
        client_id = f"conflict-{uuid.uuid4()}"
        payload = {
            "client_id": client_id,
            "is_offline_sync": True,
            "items": [{"productId": str(self.product2.id), "quantity": 15}],  # Exceeds 10 available
            "payment_method": "cash",
        }
        res = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data.get("conflicts", [])), 1)
        self.assertEqual(data["conflicts"][0]["deficit"], 5)

        # Order must be recorded and not dropped!
        order = Order.objects.get(client_id=client_id)
        self.assertIn("oversold by 5", order.note)

        # Product stock reflects -5
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock, -5)

    def test_bootstrap_sync_api(self):
        res = self.client.get("/api/sync/bootstrap")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("products", data)
        self.assertIn("categories", data)
        self.assertIn("customers", data)
        self.assertIn("settings", data)
        self.assertIn("payment_accounts", data)
        self.assertGreaterEqual(len(data["products"]), 2)
        self.assertGreaterEqual(len(data["categories"]), 1)
        self.assertGreaterEqual(len(data["customers"]), 1)
        self.assertGreaterEqual(len(data["payment_accounts"]), 5)
        self.assertEqual(data["settings"]["currency_symbol"], "$")

    def test_payment_accounts_crud_and_seed(self):
        User = get_user_model()
        user = User.objects.create_user(username="testadmin", email="testadmin@example.com", password="password", role="admin")
        self.client.force_login(user)

        # 1. Verify default seeded accounts (Meezan, Allied, HBL, Easypaisa, JazzCash)
        PaymentAccount.seed_default_accounts_if_empty()
        accounts = PaymentAccount.objects.all()
        self.assertGreaterEqual(accounts.count(), 5)
        self.assertTrue(PaymentAccount.objects.filter(name__icontains="Meezan").exists())
        self.assertTrue(PaymentAccount.objects.filter(name__icontains="Easypaisa").exists())

        # 2. Test create new bank via API
        create_res = self.client.post("/settings/payment-accounts/create", data={
            "category": "bank",
            "name": "Standard Chartered",
            "account_name": "Test POS Store",
            "account_number": "SC0001234567890",
            "is_default": "true"
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(create_res.status_code, 200)
        sc_acc = PaymentAccount.objects.get(name="Standard Chartered")
        self.assertEqual(sc_acc.category, "bank")
        self.assertTrue(sc_acc.is_default)

        # 3. Test toggle active status
        toggle_res = self.client.post(f"/settings/payment-accounts/{sc_acc.id}/toggle", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(toggle_res.status_code, 200)
        sc_acc.refresh_from_db()
        self.assertFalse(sc_acc.is_active)

        # 4. Test delete
        del_res = self.client.post(f"/settings/payment-accounts/{sc_acc.id}/delete", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(PaymentAccount.objects.filter(id=sc_acc.id).exists())

    def test_full_payment_bank_and_wallet(self):
        PaymentAccount.seed_default_accounts_if_empty()
        meezan = PaymentAccount.objects.filter(category="bank").first()
        easypaisa = PaymentAccount.objects.filter(category="wallet").first()

        # Checkout with Bank
        res_bank = self.client.post("/api/checkout", data=json.dumps({
            "items": [{"productId": str(self.product1.id), "quantity": 1}],
            "payment_method": "bank",
            "bank_account_id": str(meezan.id),
            "bank_account_name": meezan.name,
            "bank_ref": "AUTH-7788",
        }), content_type="application/json")
        self.assertEqual(res_bank.status_code, 200)
        ord_bank = Order.objects.get(id=res_bank.json()["order"]["id"])
        self.assertEqual(ord_bank.payment_method, "bank")
        self.assertEqual(ord_bank.payments.count(), 1)
        p_bank = ord_bank.payments.first()
        self.assertEqual(p_bank.account, meezan)
        self.assertEqual(p_bank.reference, "AUTH-7788")

        # Checkout with Wallet
        res_wallet = self.client.post("/api/checkout", data=json.dumps({
            "items": [{"productId": str(self.product1.id), "quantity": 1}],
            "payment_method": "wallet",
            "wallet_account_id": str(easypaisa.id),
            "wallet_account_name": easypaisa.name,
            "wallet_ref": "EP-TRX-101",
        }), content_type="application/json")
        self.assertEqual(res_wallet.status_code, 200)
        ord_wallet = Order.objects.get(id=res_wallet.json()["order"]["id"])
        self.assertEqual(ord_wallet.payment_method, "wallet")
        self.assertEqual(ord_wallet.payments.count(), 1)
        p_wallet = ord_wallet.payments.first()
        self.assertEqual(p_wallet.account, easypaisa)
        self.assertEqual(p_wallet.reference, "EP-TRX-101")

    def test_split_payment_multi_tender(self):
        PaymentAccount.seed_default_accounts_if_empty()
        bank_acc = PaymentAccount.objects.filter(category="bank").first()
        wallet_acc = PaymentAccount.objects.filter(category="wallet").first()

        # Product1 price = 2.50. Let's purchase 4 items -> Subtotal = 10.00
        # Tax = 8% -> 0.80. Discount = 0.80 -> Total = 10.00 exactly.
        # Split tender: $3.00 Cash (tendered $5.00, change $2.00), $4.00 Bank, $3.00 Wallet. Total = $10.00.
        payload = {
            "items": [{"productId": str(self.product1.id), "quantity": 4}],
            "tax_rate": 8.0,
            "discount": 0.80,
            "payment_method": "split",
            "payments": [
                {
                    "payment_method": "cash",
                    "amount": 3.00,
                    "tendered": 5.00,
                    "change": 2.00,
                    "account_name": "Cash",
                },
                {
                    "payment_method": "bank",
                    "amount": 4.00,
                    "account_id": str(bank_acc.id),
                    "account_name": bank_acc.name,
                    "account_title": bank_acc.account_name,
                    "account_number": bank_acc.account_number,
                    "reference": "BANK-SPLIT-99",
                },
                {
                    "payment_method": "wallet",
                    "amount": 3.00,
                    "account_id": str(wallet_acc.id),
                    "account_name": wallet_acc.name,
                    "account_title": wallet_acc.account_name,
                    "account_number": wallet_acc.account_number,
                    "reference": "WAL-SPLIT-88",
                }
            ],
            "note": "Customer requested 3-way split payment",
        }

        res = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        order_dict = data["order"]
        self.assertEqual(order_dict["total"], 10.00)
        self.assertEqual(order_dict["payment_method"], "split")

        # Verify payments inside order dict
        self.assertIn("payments", order_dict)
        self.assertEqual(len(order_dict["payments"]), 3)

        # Verify DB records
        order = Order.objects.get(id=order_dict["id"])
        self.assertEqual(order.payment_method, "split")
        self.assertEqual(order.payments.count(), 3)

        cash_p = order.payments.get(payment_method="cash")
        self.assertEqual(cash_p.amount, Decimal("3.00"))
        self.assertEqual(cash_p.tendered, Decimal("5.00"))
        self.assertEqual(cash_p.change, Decimal("2.00"))

        bank_p = order.payments.get(payment_method="bank")
        self.assertEqual(bank_p.amount, Decimal("4.00"))
        self.assertEqual(bank_p.account, bank_acc)
        self.assertEqual(bank_p.reference, "BANK-SPLIT-99")

        wallet_p = order.payments.get(payment_method="wallet")
        self.assertEqual(wallet_p.amount, Decimal("3.00"))
        self.assertEqual(wallet_p.account, wallet_acc)
        self.assertEqual(wallet_p.reference, "WAL-SPLIT-88")

        # Verify note contains split breakdown
        self.assertIn("Split Tender", order.note)
        self.assertIn("$3.00", order.note)
        self.assertIn(bank_acc.name, order.note)
        self.assertIn(wallet_acc.name, order.note)

    def test_full_bank_payment_checkout(self):
        bank_acc = PaymentAccount.objects.create(
            category="bank",
            name="Meezan Bank Test",
            account_name="Pulse Corp",
            account_number="PK88MEZN000123456789",
            is_active=True,
        )
        payload = {
            "items": [
                {"productId": str(self.product1.id), "quantity": 4},  # 4 * 2.50 = 10.00
            ],
            "customer_id": str(self.customer.id),
            "payment_method": "bank",
            "tax_rate": 0.0,
            "discount": 0.0,
            "payments": [
                {
                    "payment_method": "bank",
                    "amount": 10.00,
                    "account_id": str(bank_acc.id),
                    "account_name": bank_acc.name,
                    "account_title": bank_acc.account_name,
                    "account_number": bank_acc.account_number,
                    "reference": "AUTH-4242",
                    "tendered": 10.00,
                    "change": 0.00,
                }
            ],
            "note": f"[Bank: {bank_acc.name} Ref: AUTH-4242]",
        }

        res = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        order_dict = data["order"]
        self.assertEqual(order_dict["total"], 10.00)
        self.assertEqual(order_dict["payment_method"], "bank")

        order = Order.objects.get(id=order_dict["id"])
        self.assertEqual(order.payment_method, "bank")
        self.assertEqual(order.payments.count(), 1)
        bank_p = order.payments.first()
        self.assertEqual(bank_p.amount, Decimal("10.00"))
        self.assertEqual(bank_p.account, bank_acc)
        self.assertEqual(bank_p.reference, "AUTH-4242")

    def test_full_wallet_payment_checkout(self):
        wallet_acc = PaymentAccount.objects.create(
            category="wallet",
            name="Easypaisa Test",
            account_name="Cashier Mobile",
            account_number="03001234567",
            is_active=True,
        )
        payload = {
            "items": [
                {"productId": str(self.product1.id), "quantity": 2},  # 2 * 2.50 = 5.00
            ],
            "customer_id": str(self.customer.id),
            "payment_method": "wallet",
            "tax_rate": 0.0,
            "discount": 0.0,
            "payments": [
                {
                    "payment_method": "wallet",
                    "amount": 5.00,
                    "account_id": str(wallet_acc.id),
                    "account_name": wallet_acc.name,
                    "account_title": wallet_acc.account_name,
                    "account_number": wallet_acc.account_number,
                    "reference": "TRX-998877",
                    "tendered": 5.00,
                    "change": 0.00,
                }
            ],
            "note": f"[Wallet: {wallet_acc.name} Ref: TRX-998877]",
        }

        res = self.client.post("/api/checkout", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        order_dict = data["order"]
        self.assertEqual(order_dict["total"], 5.00)
        self.assertEqual(order_dict["payment_method"], "wallet")

        order = Order.objects.get(id=order_dict["id"])
        self.assertEqual(order.payment_method, "wallet")
        self.assertEqual(order.payments.count(), 1)
        wallet_p = order.payments.first()
        self.assertEqual(wallet_p.amount, Decimal("5.00"))
        self.assertEqual(wallet_p.account, wallet_acc)
        self.assertEqual(wallet_p.reference, "TRX-998877")



