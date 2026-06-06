import math

import frappe


def get_context(context):
    page = frappe.form_dict.get("page")
    page = int(page) if page and str(page).isdigit() else 1

    page_length = 6
    group = frappe.form_dict.get("group")

    filters = {"disabled": 0}
    if group:
        filters["item_group"] = group

    total_items = frappe.db.count("Item", filters)
    total_pages = max(1, math.ceil(total_items / page_length))
    page = max(1, min(page, total_pages))

    items = frappe.get_all(
        "Item",
        fields=[
            "name",
            "item_name",
            "item_group",
            "description",
            "image",
            "custom_is_trendy",
            "custom_just_arrived",
            "custom_image_2",
        ],
        filters=filters,
        order_by="item_name asc",
        limit_start=(page - 1) * page_length,
        limit_page_length=page_length,
    )

    prices = frappe.get_all(
        "Item Price",
        fields=["item_code", "price_list_rate", "custom_price_before"],
        filters={"selling": 1},
    )
    price_map = {p.item_code: p for p in prices}

    for item in items:
        p = price_map.get(item.name)
        item.selling_price = p.price_list_rate if p else None
        item.custom_price_before = p.custom_price_before if p else None

    modal_products = []
    for item in items:
        images = [
            image
            for image in [item.image, item.custom_image_2]
            if image
        ] or ["/assets/shop_xi/images/product-01.jpg"]

        modal_products.append(
            {
                "name": item.name,
                "title": item.item_name or item.name,
                "price": item.selling_price,
                "description": item.description or "",
                "images": images,
            }
        )

    item_groups = frappe.get_all(
        "Item Group",
        fields=["name", "item_group_name", "image"],
        filters={"custom_disabled": 0},
        order_by="item_group_name asc",
    )

    context.items = items
    context.modal_products = modal_products
    context.item_groups = item_groups
    context.current_page = page
    context.total_pages = total_pages
    context.selected_group = group
    context.has_prev = page > 1
    context.has_next = page < total_pages
    context.show_pagination = total_pages > 1

    return context
