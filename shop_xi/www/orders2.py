import frappe
from frappe.utils import flt, formatdate


def money(value):
    return "${:,.2f}".format(flt(value))


def get_user_email(user):
    return frappe.db.get_value("User", user, "email") or user


def get_linked_customers(user):
    user_email = get_user_email(user)
    customers = set(frappe.get_all(
        "Customer",
        filters={"email_id": user_email},
        pluck="name",
    ))

    try:
        contacts = frappe.get_all(
            "Contact Email",
            filters={"email_id": user_email},
            pluck="parent",
        )
        if contacts:
            customers.update(frappe.get_all(
                "Dynamic Link",
                filters={
                    "parenttype": "Contact",
                    "parent": ["in", contacts],
                    "link_doctype": "Customer",
                },
                pluck="link_name",
            ))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Orders customer lookup failed")

    return list(customers)


def get_invoice_fields():
    return [
        "name",
        "posting_date",
        "grand_total",
        "outstanding_amount",
        "status",
        "customer",
    ]


def get_user_invoices(user, customers):
    invoice_map = {}
    base_filters = {"docstatus": ["<", 2]}

    def add_invoices(filters):
        for invoice in frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=get_invoice_fields(),
            order_by="posting_date desc, creation desc",
        ):
            invoice_map[invoice.name] = invoice

    if customers:
        add_invoices({
            **base_filters,
            "customer": ["in", customers],
        })

    add_invoices({
        **base_filters,
        "owner": user,
    })

    user_email = get_user_email(user)

    if frappe.get_meta("Sales Invoice").has_field("contact_email"):
        add_invoices({
            **base_filters,
            "contact_email": user_email,
        })

    return sorted(
        invoice_map.values(),
        key=lambda invoice: (invoice.posting_date, invoice.name),
        reverse=True,
    )


def get_invoice_items(invoice_name):
    items = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": invoice_name},
        fields=["item_code", "item_name", "qty", "rate", "amount"],
        order_by="idx asc",
    )

    return [
        {
            "item": item.item_name or item.item_code,
            "qty": item.qty,
            "rate": money(item.rate),
            "total": money(item.amount),
        }
        for item in items
    ]


def get_context(context):
    user = frappe.session.user

    context.login_required = user == "Guest"
    context.orders = []

    if context.login_required:
        return context

    customers = get_linked_customers(user)
    invoices = get_user_invoices(user, customers)

    for invoice in invoices:
        items = get_invoice_items(invoice.name)
        status = invoice.status or ("Paid" if flt(invoice.outstanding_amount) <= 0 else "Unpaid")

        context.orders.append({
            "name": invoice.name,
            "date": formatdate(invoice.posting_date),
            "status": status,
            "is_paid": flt(invoice.outstanding_amount) <= 0 or status == "Paid",
            "total": money(invoice.grand_total),
            "amount": flt(invoice.grand_total),
            "items_summary": ", ".join(item["item"] for item in items) or "No items",
            "items_json": frappe.as_json(items),
        })

    return context
