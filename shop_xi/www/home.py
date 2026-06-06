from urllib.parse import urlencode

import frappe


DEFAULT_CATEGORY_IMAGES = [
	"/assets/shop_xi/images/banner-04.jpg",
	"/assets/shop_xi/images/banner-05.jpg",
	"/assets/shop_xi/images/banner-07.jpg",
	"/assets/shop_xi/images/banner-08.jpg",
	"/assets/shop_xi/images/banner-09.jpg",
]


def get_context(context):
	context.home_categories = get_home_categories()
	context.product_category_links = get_home_category_links()
	context.trendy_items = get_trendy_items()
	context.trendy_modal_products = get_modal_products(context.trendy_items)
	return context


def get_home_categories(limit=5):
	filters = {}
	meta = frappe.get_meta("Item Group")

	if meta.has_field("custom_disabled"):
		filters["custom_disabled"] = 0

	item_groups = frappe.get_all(
		"Item Group",
		fields=["name", "item_group_name", "image"],
		filters=filters,
		order_by="item_group_name asc",
		limit_page_length=limit,
	)

	categories = []
	for index, group in enumerate(item_groups):
		label = group.item_group_name or group.name
		categories.append(
			{
				"label": label,
				"image": group.image or DEFAULT_CATEGORY_IMAGES[index % len(DEFAULT_CATEGORY_IMAGES)],
				"url": "/products?" + urlencode({"group": group.name}),
				"info": "Shop Collection",
			}
		)

	return categories or get_fallback_categories()


def get_home_category_links(limit=50):
	categories = get_home_categories(limit=limit)
	return [{"label": "All Products", "url": "/products"}] + [
		{
			"label": category["label"],
			"url": category["url"],
		}
		for category in categories
	]


def get_trendy_items(limit=8):
	meta = frappe.get_meta("Item")
	trendy_field = get_trendy_field(meta)

	if not trendy_field:
		return []

	fields = [
		"name",
		"item_name",
		"item_group",
		"description",
		"image",
		"creation",
	]

	if meta.has_field("custom_image_2"):
		fields.append("custom_image_2")

	items = frappe.get_all(
		"Item",
		fields=fields,
		filters={
			"disabled": 0,
			trendy_field: 1,
		},
		order_by="modified desc",
		limit_page_length=limit,
	)

	prices = frappe.get_all(
		"Item Price",
		fields=["item_code", "price_list_rate", "custom_price_before"],
		filters={"selling": 1},
	)
	price_map = {price.item_code: price for price in prices}

	for item in items:
		price = price_map.get(item.name)
		item.selling_price = price.price_list_rate if price else None
		item.custom_price_before = price.custom_price_before if price else None

	return items


def get_trendy_field(meta):
	if meta.has_field("is_trendy"):
		return "is_trendy"

	if meta.has_field("custom_is_trendy"):
		return "custom_is_trendy"

	return None


def get_modal_products(items):
	products = []

	for item in items:
		images = [
			image
			for image in [
				item.image,
				item.get("custom_image_2"),
			]
			if image
		] or ["/assets/shop_xi/images/product-01.jpg"]

		products.append(
			{
				"name": item.name,
				"title": item.item_name or item.name,
				"price": item.selling_price,
				"description": item.description or "",
				"images": images,
			}
		)

	return products


def get_fallback_categories():
	labels = ["Women", "Men", "Watches", "Bags", "Accessories"]
	return [
		{
			"label": label,
			"image": DEFAULT_CATEGORY_IMAGES[index],
			"url": "/products?" + urlencode({"group": label}),
			"info": "Shop Collection",
		}
		for index, label in enumerate(labels)
	]
