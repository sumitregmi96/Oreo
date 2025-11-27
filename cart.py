import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import io
import requests
import os
from checkout import CheckoutWindow
from database import connect_db

BG_MAIN = "#050505"
BG_PANEL = "#151515"
FG_TEXT = "#FFFFFF"
ACCENT = "#FF3B3B"


class CartWindow(tk.Toplevel):
    def __init__(self, parent, user_id):
        super().__init__(parent)
        self.title("Your Cart - Oreo POS")
        self.geometry("900x600")
        self.config(bg=BG_MAIN)
        self.user_id = user_id

        # Header
        header = tk.Frame(self, bg=BG_MAIN)
        header.pack(fill="x", pady=10, padx=20)
        tk.Label(
            header,
            text="Current Sale Cart 🛒",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Arial", 18, "bold"),
        ).pack(side="left")
        tk.Button(
            header,
            text="Close",
            bg=ACCENT,
            fg="white",
            font=("Arial", 10, "bold"),
            relief="flat",
            command=self.destroy,
        ).pack(side="right")

        # Frames
        self.items_frame = tk.Frame(self, bg=BG_MAIN)
        self.items_frame.pack(side="left", fill="y", padx=20, pady=20)

        self.checkout_frame = tk.Frame(self, bg=BG_PANEL, width=300, height=500)
        self.checkout_frame.pack(side="right", padx=20, pady=20, fill="both", expand=True)
        self.checkout_frame.pack_propagate(False)

        tk.Label(
            self.checkout_frame,
            text="Summary",
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Arial", 14, "bold"),
        ).pack(anchor="nw", pady=10, padx=10)

        self.checkout_items = tk.Frame(self.checkout_frame, bg=BG_PANEL)
        self.checkout_items.pack(anchor="nw", padx=10)

        self.total_label = tk.Label(
            self.checkout_frame,
            text="Total: $0.00",
            bg=BG_PANEL,
            fg=ACCENT,
            font=("Arial", 14, "bold"),
        )
        self.total_label.pack(anchor="s", pady=10)

        tk.Button(
            self.checkout_frame,
            text="Proceed to Checkout",
            bg=ACCENT,
            fg="white",
            font=("Arial", 12, "bold"),
            relief="flat",
            command=self.checkout,
        ).pack(side="bottom", pady=20)

        self.load_cart()

    # ---------- Load Cart ----------
    def load_cart(self):
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT c.cart_id, c.quantity, p.product_id, p.name, p.price, p.image_url
            FROM cart c
            JOIN product p ON c.product_id = p.product_id
            WHERE c.user_id=%s
        """,
            (self.user_id,),
        )
        cart_items = cursor.fetchall()
        db.close()

        # Clear previous widgets
        for widget in self.items_frame.winfo_children():
            widget.destroy()
        for widget in self.checkout_items.winfo_children():
            widget.destroy()

        if not cart_items:
            tk.Label(
                self.items_frame,
                text="Cart is empty",
                bg=BG_MAIN,
                fg=FG_TEXT,
                font=("Arial", 12, "bold"),
            ).pack()
            self.total_label.config(text="Total: $0.00")
            self.total_price = 0
            return

        self.total_price = 0
        for item in cart_items:
            cart_id, quantity, product_id, name, price, image_url = item
            self.total_price += price * quantity

            frame = tk.Frame(self.items_frame, bg=BG_MAIN, pady=10)
            frame.pack(anchor="nw", fill="x")

            # Load image
            try:
                if image_url and os.path.exists(image_url):
                    img = Image.open(image_url)
                else:
                    response = requests.get(image_url, timeout=5)
                    img = Image.open(io.BytesIO(response.content))
                img = img.resize((80, 80))
                photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error loading image for {name}: {e}")
                img = Image.new("RGB", (80, 80), color="grey")
                photo = ImageTk.PhotoImage(img)

            lbl_img = tk.Label(frame, image=photo, bg=BG_MAIN)
            lbl_img.image = photo
            lbl_img.pack(side="left")

            info_frame = tk.Frame(frame, bg=BG_MAIN)
            info_frame.pack(side="left", padx=10)

            tk.Label(
                info_frame,
                text=name,
                bg=BG_MAIN,
                fg=FG_TEXT,
                font=("Arial", 12, "bold"),
            ).pack(anchor="w")
            tk.Label(
                info_frame,
                text=f"Price: ${price:.2f}",
                bg=BG_MAIN,
                fg="#BBBBBB",
                font=("Arial", 12),
            ).pack(anchor="w")
            tk.Label(
                info_frame,
                text=f"Quantity: {quantity}",
                bg=BG_MAIN,
                fg=FG_TEXT,
                font=("Arial", 12),
            ).pack(anchor="w")

            btn_row = tk.Frame(info_frame, bg=BG_MAIN)
            btn_row.pack(anchor="w", pady=5)

            tk.Button(
                btn_row,
                text="+",
                bg="#252525",
                fg=FG_TEXT,
                font=("Arial", 12),
                relief="flat",
                command=lambda cid=cart_id: self.add_quantity(cid),
            ).pack(side="left", padx=(0, 5))

            tk.Button(
                btn_row,
                text="Remove",
                bg=ACCENT,
                fg="white",
                font=("Arial", 11),
                relief="flat",
                command=lambda cid=cart_id: self.remove_item(cid),
            ).pack(side="left")

            # Add to checkout summary
            tk.Label(
                self.checkout_items,
                text=f"{name} × {quantity} ........... ${price*quantity:.2f}",
                bg=BG_PANEL,
                fg=FG_TEXT,
                font=("Arial", 12),
            ).pack(anchor="w")

        self.total_label.config(text=f"Total: ${self.total_price:.2f}")

    # ---------- Add Quantity ----------
    def add_quantity(self, cart_id):
        db = connect_db()
        cursor = db.cursor()
        try:
            db.start_transaction()
            # Get the product for this cart line and lock rows
            cursor.execute(
                "SELECT product_id FROM cart WHERE cart_id=%s AND user_id=%s FOR UPDATE",
                (cart_id, self.user_id),
            )
            row = cursor.fetchone()
            if not row:
                raise Exception("Cart item not found.")
            product_id = row[0]

            cursor.execute(
                "SELECT stock, name FROM product WHERE product_id=%s FOR UPDATE",
                (product_id,),
            )
            prow = cursor.fetchone()
            if not prow:
                raise Exception("Product not found.")
            stock, pname = prow
            if (stock or 0) <= 0:
                raise Exception(f"{pname} is out of stock.")

            # Reserve one more unit and bump quantity
            cursor.execute(
                "UPDATE product SET stock = stock - 1 WHERE product_id=%s",
                (product_id,),
            )
            cursor.execute(
                "UPDATE cart SET quantity = quantity + 1 WHERE cart_id=%s",
                (cart_id,),
            )
            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            messagebox.showerror("Cart", str(e))
        finally:
            db.close()
            self.load_cart()

    # ---------- Remove Item ----------
    def remove_item(self, cart_id):
        db = connect_db()
        cursor = db.cursor()
        try:
            db.start_transaction()
            # Find quantity and product, lock the cart row
            cursor.execute(
                "SELECT product_id, quantity FROM cart WHERE cart_id=%s AND user_id=%s FOR UPDATE",
                (cart_id, self.user_id),
            )
            row = cursor.fetchone()
            if row:
                product_id, qty = row
                # Return reserved stock
                cursor.execute(
                    "UPDATE product SET stock = stock + %s WHERE product_id=%s",
                    (qty, product_id),
                )
                cursor.execute("DELETE FROM cart WHERE cart_id=%s", (cart_id,))
            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            messagebox.showerror("Cart", str(e))
        finally:
            db.close()
            self.load_cart()

    # ---------- Checkout ----------
    def checkout(self):
        if getattr(self, "total_price", 0) == 0:
            messagebox.showwarning(
                "Cart Empty", "Your cart is empty. Add items before checkout!"
            )
            return
        CheckoutWindow(self, self.user_id)
