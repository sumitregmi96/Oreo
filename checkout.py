import tkinter as tk
from tkinter import messagebox, simpledialog
from PIL import Image, ImageTk
from datetime import datetime
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from database import record_order_effects, connect_db, get_user_stats

# ---- POS / Store Settings ----
BG_MAIN = "#050505"
BG_CARD = "#151515"
FG_TEXT = "#FFFFFF"
ACCENT = "#FF3B3B"

STORE_NAME = "Oreo Electronics"
STORE_ADDRESS = "123 Tech Street, Auckland"
TAX_RATE = 0.15        # 15% tax (change if you want)


class CheckoutWindow(tk.Toplevel):
    def __init__(self, parent, user_id):
        super().__init__(parent)
        self.title("Checkout - Oreo POS")
        self.geometry("1000x600")
        self.config(bg=BG_MAIN)
        self.user_id = user_id  # staff user id

        # Header
        tk.Label(
            self,
            text="Checkout 🛒",
            font=("Arial", 18, "bold"),
            bg=BG_MAIN,
            fg=ACCENT,
        ).pack(pady=10)

        tk.Button(
            self,
            text="Close",
            bg=ACCENT,
            fg="white",
            font=("Arial", 10, "bold"),
            relief="flat",
            command=self.destroy,
        ).place(x=900, y=10)

        main_frame = tk.Frame(self, bg=BG_MAIN)
        main_frame.pack(expand=True, fill="both", padx=20)

        # Receipt Panel
        receipt_frame = tk.Frame(main_frame, bg=BG_CARD, width=450, height=500)
        receipt_frame.pack(side="left", padx=10, pady=10)
        receipt_frame.pack_propagate(False)

        tk.Label(
            receipt_frame,
            text="Receipt",
            bg=BG_CARD,
            fg=FG_TEXT,
            font=("Arial", 14, "bold"),
        ).pack(pady=10)

        self.items_box = tk.Frame(receipt_frame, bg=BG_CARD)
        self.items_box.pack(anchor="nw", padx=20)

        self.total_label = tk.Label(
            receipt_frame,
            text="Total: $0.00",
            bg=BG_CARD,
            fg=ACCENT,
            font=("Arial", 14, "bold"),
        )
        self.total_label.pack(side="bottom", pady=20)

        # Payment Panel
        pay_frame = tk.Frame(main_frame, bg=BG_MAIN)
        pay_frame.pack(side="left", padx=40)

        tk.Label(
            pay_frame,
            text="Payment Method",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Arial", 14, "bold"),
        ).pack(anchor="nw")

        # Card Image
        try:
            img = Image.open("visa.png").resize((120, 80))
            card_img = ImageTk.PhotoImage(img)
        except Exception:
            img = Image.new("RGB", (120, 80), "grey")
            card_img = ImageTk.PhotoImage(img)

        tk.Label(pay_frame, image=card_img, bg=BG_MAIN).pack(pady=10)
        self.card_img = card_img

        # Card Inputs
        self.card_entry = tk.Entry(
            pay_frame,
            width=30,
            bg="#222222",
            fg="white",
            insertbackground="white",
        )
        self.card_entry.insert(0, "Card Number")
        self.card_entry.pack(pady=5)

        card_row = tk.Frame(pay_frame, bg=BG_MAIN)
        card_row.pack(pady=5)

        self.cvv_entry = tk.Entry(
            card_row,
            width=10,
            bg="#222222",
            fg="white",
            insertbackground="white",
        )
        self.cvv_entry.insert(0, "CVV")
        self.cvv_entry.pack(side="left", padx=5)

        self.exp_entry = tk.Entry(
            card_row,
            width=15,
            bg="#222222",
            fg="white",
            insertbackground="white",
        )
        self.exp_entry.insert(0, "mm/yyyy")
        self.exp_entry.pack(side="left", padx=5)

        tk.Button(
            pay_frame,
            text="Checkout",
            bg=ACCENT,
            fg="white",
            font=("Arial", 12, "bold"),
            relief="flat",
            command=self.process_checkout,
        ).pack(pady=20)

        self.load_cart()

    # ----------------- PAYMENT VALIDATION -----------------
    def _validate_payment_inputs(self):
        card = (self.card_entry.get() or "").replace(" ", "")
        cvv = (self.cvv_entry.get() or "").strip()
        exp = (self.exp_entry.get() or "").strip()

        # if not card.isdigit() or len(card) not in (13, 15, 16):
        #     messagebox.showerror("Payment Error", "Invalid card number.")
        #     return False
        # if not cvv.isdigit() or len(cvv) not in (3, 4):
        #     messagebox.showerror("Payment Error", "Invalid CVV.")
        #     return False
        # try:
        #     mm, yyyy = exp.split("/")
        #     mm = int(mm)
        #     yyyy = int(yyyy)
        #     if mm < 1 or mm > 12:
        #         raise ValueError
        #     now = datetime.now()
        #     if (yyyy < now.year) or (yyyy == now.year and mm < now.month):
        #         messagebox.showerror("Payment Error", "Card is expired.")
        #         return False
        # except Exception:
        #     messagebox.showerror("Payment Error", "Expiry must be in mm/yyyy format.")
        #     return False
        return True

    # ----------------- LOAD CART -----------------
    def load_cart(self):
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT c.product_id, c.quantity, p.name, p.price 
            FROM cart c JOIN product p 
            ON c.product_id = p.product_id
            WHERE c.user_id = %s
        """,
            (self.user_id,),
        )
        self.cart_items = cursor.fetchall()
        db.close()

        total = 0
        for p in self.cart_items:
            pid, qty, name, price = p
            total += price * qty
            tk.Label(
                self.items_box,
                text=f"{name} x {qty} ...... ${price*qty:.2f}",
                bg=BG_CARD,
                fg=FG_TEXT,
                font=("Arial", 12),
            ).pack(anchor="w")

        self.subtotal = total
        self.total_label.config(text=f"Total: ${total:.2f}")

    # ----------------- PDF RECEIPT GENERATOR -----------------
    def _generate_receipt_pdf(
        self,
        order_id,
        items,
        subtotal,
        tax_amount,
        discount_amount,
        net_amount,
        member_profile,
    ):
        """
        items: list of dicts -> {name, qty, unit_price, line_total}
        member_profile: dict or None
        """
        os.makedirs("receipts", exist_ok=True)
        filename = os.path.join("receipts", f"receipt_{order_id}.pdf")

        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4

        y = height - 40

        # Header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, STORE_NAME)
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawString(50, y, STORE_ADDRESS)
        y -= 20
        c.drawString(50, y, f"Order ID: {order_id}")
        y -= 15
        c.drawString(50, y, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        y -= 20

        # Member Info
        if member_profile:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, "Member:")
            y -= 14
            c.setFont("Helvetica", 10)
            c.drawString(60, y, f"Name: {member_profile['name']}")
            y -= 14
            c.drawString(60, y, f"Member No: {member_profile['member_number']}")
            y -= 14
            c.drawString(60, y, f"Level: {member_profile['membership_level']}")
            y -= 14
            c.drawString(60, y, f"Points: {member_profile['points']}")
            y -= 20

        # Line
        c.line(50, y, width - 50, y)
        y -= 20

        # Table Header
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Item")
        c.drawString(260, y, "Qty")
        c.drawString(310, y, "Unit")
        c.drawString(380, y, "Total")
        y -= 15
        c.line(50, y, width - 50, y)
        y -= 15

        # Items
        c.setFont("Helvetica", 10)
        for item in items:
            if y < 100:  # new page if too low
                c.showPage()
                y = height - 40
            name = item["name"]
            qty = item["qty"]
            unit = item["unit_price"]
            line_total = item["line_total"]

            c.drawString(50, y, name[:30])  # truncate if long
            c.drawString(260, y, str(qty))
            c.drawString(310, y, f"${unit:.2f}")
            c.drawString(380, y, f"${line_total:.2f}")
            y -= 14

        y -= 10
        c.line(50, y, width - 50, y)
        y -= 20

        # Summary
        c.setFont("Helvetica-Bold", 11)
        c.drawString(300, y, f"Subtotal: ${subtotal:.2f}")
        y -= 15
        c.drawString(300, y, f"Tax ({int(TAX_RATE*100)}%): ${tax_amount:.2f}")
        y -= 15
        c.drawString(300, y, f"Discount: -${discount_amount:.2f}")
        y -= 15
        c.drawString(300, y, f"Total Due: ${net_amount:.2f}")
        y -= 25

        c.setFont("Helvetica", 9)
        c.drawString(50, y, "Thank you for shopping with us!")

        c.save()
        return filename

    # ----------------- PROCESS CHECKOUT -----------------
    def process_checkout(self):
        if not self.cart_items:
            messagebox.showwarning("Warning", "Cart is empty!")
            return
        if not self._validate_payment_inputs():
            return

        # Ask for member number (can be blank for no membership)
        member_number = simpledialog.askstring(
            "Member Number",
            "Enter customer member number (leave blank if no membership):",
            parent=self,
        )
        member_number = (member_number or "").strip()

        db = connect_db()
        cursor = db.cursor()

        member_id = None
        membership_level = None
        discount_rate = 0.0

        try:
            # -------- Fetch member (if any) --------
            if member_number:
                cursor.execute(
                    """
                    SELECT user_id, membership_level, COALESCE(total_spent,0)
                    FROM users
                    WHERE member_number=%s AND role='member'
                    """,
                    (member_number,),
                )
                row = cursor.fetchone()
                if row:
                    member_id, membership_level, total_spent = row
                    level = membership_level or "Bronze"
                    if level == "Gold":
                        discount_rate = 0.15
                    elif level == "Silver":
                        discount_rate = 0.10
                    elif level == "Bronze":
                        discount_rate = 0.05
                else:
                    messagebox.showinfo(
                        "Member Not Found",
                        "No member found with that number. Proceeding without discount.",
                    )

            # -------- Transaction: create order --------
            db.start_transaction()

            # Refresh latest cart from DB and lock cart rows
            cursor.execute(
                """
                SELECT c.product_id, c.quantity, p.name, p.price
                FROM cart c
                JOIN product p ON c.product_id = p.product_id
                WHERE c.user_id = %s FOR UPDATE
                """,
                (self.user_id,),
            )
            items = cursor.fetchall()
            if not items:
                raise Exception("Cart became empty.")

            # Build item objects and compute subtotal
            subtotal = 0.0
            receipt_items = []
            for pid, qty, name, price in items:
                line_total = float(price) * int(qty)
                subtotal += line_total
                receipt_items.append(
                    {
                        "name": name,
                        "qty": int(qty),
                        "unit_price": float(price),
                        "line_total": line_total,
                    }
                )

            tax_amount = subtotal * TAX_RATE
            discount_amount = subtotal * discount_rate
            net_amount = subtotal + tax_amount - discount_amount

            # Create order
            cursor.execute(
                """
                INSERT INTO orders (user_id, member_id, total_amount, discount_amount, net_amount, status)
                VALUES (%s, %s, %s, %s, %s, 'Pending')
                """,
                (self.user_id, member_id, subtotal, discount_amount, net_amount),
            )
            order_id = cursor.lastrowid

            # Insert order_items
            for item in receipt_items:
                cursor.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (order_id, items[receipt_items.index(item)][0], item["qty"], item["unit_price"]),
                )

            # Payment record (net amount charged)
            cursor.execute(
                """
                INSERT INTO payment (order_id, payment_method, amount, status)
                VALUES (%s, 'Card', %s, 'Completed')
                """,
                (order_id, net_amount),
            )

            # Clear cart for staff
            cursor.execute("DELETE FROM cart WHERE user_id=%s", (self.user_id,))

            # Mark order Processing to indicate payment captured
            cursor.execute(
                "UPDATE orders SET status='Processing' WHERE order_id=%s",
                (order_id,),
            )

            db.commit()

            # -------- Update loyalty (member spend/tier) --------
            member_profile = None
            if member_id:
                try:
                    record_order_effects(order_id)  # updates total_spent + membership_level
                    # Get updated stats
                    stats = get_user_stats(member_id)
                    # Fetch name + member_number
                    db2 = connect_db()
                    cur2 = db2.cursor()
                    cur2.execute(
                        "SELECT username, member_number FROM users WHERE user_id=%s",
                        (member_id,),
                    )
                    row = cur2.fetchone()
                    db2.close()
                    if row:
                        name, mnum = row
                    else:
                        name, mnum = "Unknown", ""
                    # Simple points system: 1 point per $1 spent total
                    points = int(stats["total_spent"])
                    member_profile = {
                        "name": name,
                        "member_number": mnum or member_number,
                        "membership_level": stats["membership_level"],
                        "points": points,
                    }
                except Exception:
                    member_profile = None
            else:
                # no membership
                member_profile = None

            # -------- Generate PDF Receipt --------
            pdf_path = self._generate_receipt_pdf(
                order_id=order_id,
                items=receipt_items,
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                net_amount=net_amount,
                member_profile=member_profile,
            )

            # -------- Final message --------
            msg = f"Order #{order_id} placed successfully!\n\n"
            msg += f"Subtotal: ${subtotal:.2f}\n"
            msg += f"Tax ({int(TAX_RATE*100)}%): ${tax_amount:.2f}\n"
            if member_id and discount_rate > 0:
                msg += f"Discount ({int(discount_rate*100)}%): -${discount_amount:.2f}\n"
            msg += f"Total Paid: ${net_amount:.2f}\n\n"
            msg += f"Receipt saved as:\n{pdf_path}"
            if member_profile:
                msg += f"\n\nMember Points: {member_profile['points']} (Level: {member_profile['membership_level']})"

            messagebox.showinfo("Success", msg)
            self.destroy()

        except Exception as err:
            try:
                db.rollback()
            except Exception:
                pass
            messagebox.showerror("Checkout Failed", str(err))
        finally:
            db.close()
