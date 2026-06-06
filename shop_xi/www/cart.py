import frappe
from frappe.utils import cint, flt


def get_identity(guest_id=None):
    user = frappe.session.user

    if user != "Guest":
        return user

    return guest_id or frappe.request.cookies.get("guest_id")


def get_cart_amount(qty, rate):
    return flt(qty) * flt(rate)


@frappe.whitelist(allow_guest=True)
def get_cart_count(guest_id=None):
    identity = get_identity(guest_id)

    if not identity:
        return {"cart_count": 0}

    return {
        "cart_count": frappe.db.count("Cart Item", {"cart_owner": identity})
    }


def build_cart_item_response(cart_item):
    item_details = frappe.db.get_value(
        "Item",
        cart_item.item,
        ["item_name", "image"],
        as_dict=True,
    ) or {}
    item_name = cart_item.item_name or item_details.get("item_name") or cart_item.item
    image = cart_item.image or item_details.get("image") or "/assets/shop_xi/images/product-01.jpg"
    amount = get_cart_amount(cart_item.qty, cart_item.rate)

    return {
        "item": cart_item.item,
        "item_name": item_name,
        "qty": cart_item.qty,
        "rate": cart_item.rate,
        "amount": amount,
        "image": image,
    }


@frappe.whitelist(allow_guest=True)
def get_cart_items(guest_id=None):
    identity = get_identity(guest_id)

    if not identity:
        return {"items": [], "cart_count": 0, "total": 0}

    cart_items = frappe.get_all(
        "Cart Item",
        filters={"cart_owner": identity},
        fields=["item", "item_name", "qty", "rate", "image"],
        order_by="modified desc",
    )
    items = [build_cart_item_response(cart_item) for cart_item in cart_items]

    return {
        "items": items,
        "cart_count": len(items),
        "total": sum(item["amount"] for item in items),
    }


@frappe.whitelist(allow_guest=True)
def get_cart_item(item_code, guest_id=None):
    identity = get_identity(guest_id)

    if not identity:
        return {"in_cart": False, "qty": 0, "rate": 0, "amount": 0, "cart_count": 0}

    cart_item = frappe.db.get_value(
        "Cart Item",
        {"cart_owner": identity, "item": item_code},
        ["name", "qty", "rate"],
        as_dict=True,
    )

    return {
        "in_cart": bool(cart_item),
        "qty": cart_item.qty if cart_item else 0,
        "rate": cart_item.rate if cart_item else 0,
        "amount": get_cart_amount(cart_item.qty, cart_item.rate) if cart_item else 0,
        "cart_count": frappe.db.count("Cart Item", {"cart_owner": identity}),
    }


@frappe.whitelist(allow_guest=True)
def add_to_cart(item_code, qty=1, guest_id=None, is_set_qty=False):
    identity = get_identity(guest_id)

    if not identity:
        frappe.throw("Cart owner could not be identified")

    qty = max(cint(qty), 1)
    selling_price = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": "Standard Selling"},
        "price_list_rate",
    )

    existing = frappe.db.get_value(
        "Cart Item",
        {"cart_owner": identity, "item": item_code},
        "name",
    )

    if existing:
        doc = frappe.get_doc("Cart Item", existing)

        if str(is_set_qty).lower() in ["true", "1"]:
            doc.qty = qty
        else:
            doc.qty += qty

        doc.save(ignore_permissions=True)

        return {
            "status": "updated",
            "item": item_code,
            "qty": doc.qty,
            "rate": doc.rate,
            "amount": get_cart_amount(doc.qty, doc.rate),
            "cart_count": frappe.db.count("Cart Item", {"cart_owner": identity}),
        }

    doc = frappe.get_doc(
        {
            "doctype": "Cart Item",
            "cart_owner": identity,
            "item": item_code,
            "qty": qty,
            "rate": flt(selling_price),
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()

    return {
        "status": "created",
        "name": doc.name,
        "item": item_code,
        "qty": doc.qty,
        "rate": doc.rate,
        "amount": get_cart_amount(doc.qty, doc.rate),
        "cart_count": frappe.db.count("Cart Item", {"cart_owner": identity}),
    }


@frappe.whitelist(allow_guest=True)
def delete_from_cart(item_code, guest_id=None):
    identity = get_identity(guest_id)

    if not identity:
        frappe.throw("Cart owner could not be identified")

    existing = frappe.db.get_value(
        "Cart Item",
        {"cart_owner": identity, "item": item_code},
        "name",
    )

    if existing:
        frappe.delete_doc("Cart Item", existing, ignore_permissions=True)

    return {
        "status": "deleted" if existing else "not_found",
        "item": item_code,
        "qty": 0,
        "rate": 0,
        "amount": 0,
        "cart_count": frappe.db.count("Cart Item", {"cart_owner": identity}),
    }


def get_context(context):
    identity = get_identity(frappe.form_dict.get("guest_id"))

    context.cart = frappe.get_all(
        "Cart Item",
        filters={"cart_owner": identity},
        fields=["item", "qty", "rate", "image"],
    ) if identity else []


def merge_cart_on_login(login_manager):
    user = login_manager.user
    guest_id = frappe.request.cookies.get("guest_id")

    if not guest_id or user == "Guest" or guest_id == user:
        return

    guest_items = frappe.get_all(
        "Cart Item",
        filters={"cart_owner": guest_id},
        fields=["name", "item", "qty"],
    )

    for guest_item in guest_items:
        existing = frappe.db.get_value(
            "Cart Item",
            {"cart_owner": user, "item": guest_item.item},
            "name",
        )

        if existing:
            doc = frappe.get_doc("Cart Item", existing)
            doc.qty += guest_item.qty
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(
                {
                    "doctype": "Cart Item",
                    "cart_owner": user,
                    "item": guest_item.item,
                    "qty": guest_item.qty,
                }
            )
            doc.flags.ignore_permissions = True
            doc.insert()

        frappe.delete_doc("Cart Item", guest_item.name, ignore_permissions=True)

    frappe.db.commit()
