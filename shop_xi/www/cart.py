import frappe
from frappe.utils import cint, flt


def get_identity(guest_id=None):
    user = frappe.session.user

    if user != "Guest":
        return user

    return guest_id or frappe.request.cookies.get("guest_id")


@frappe.whitelist(allow_guest=True)
def get_cart_count(guest_id=None):
    identity = get_identity(guest_id)

    if not identity:
        return {"cart_count": 0}

    return {
        "cart_count": frappe.db.count("Cart Item", {"cart_owner": identity})
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
