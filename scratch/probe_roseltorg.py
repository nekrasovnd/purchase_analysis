from purchase_analysis.clients.roseltorg import fetch_search_page, parse_search_items

def main():
    try:
        html, url = fetch_search_page("Сбербанк", "01.01.2024", "31.12.2025", 1)
        items = parse_search_items(html, "ПАО Сбербанк", "Сбербанк")
        print(f"Success! Found {len(items)} items on page 1.")
        print(items[0] if items else "No items.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
