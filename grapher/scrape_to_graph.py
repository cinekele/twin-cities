from grapher.twin_cities_graph import TwinCitiesGraph
from scraper.scrape import Scraper


def scrape_to_graph() -> TwinCitiesGraph:
    scraper = Scraper()
    scraper.run()
    scraper.save_cities()
    twin_cities = TwinCitiesGraph(scraper.cities)
    return twin_cities


if __name__ == '__main__':
    graph = scrape_to_graph()
    graph.save("twin_cities.ttl")
    print(graph.serialize())
