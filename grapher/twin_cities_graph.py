from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS
from rdflib.term import Node

from scraper.scrape import City, TwinCitiesAgreement, Reference


class TwinCitiesGraph:
    def __init__(self, cities: list[City] = None):
        self.graph = Graph()
        self.twin_cities = Namespace("https://mini.pw.edu.pl/twin-cities#")
        self.graph.bind("twin-cities", self.twin_cities)
        self.wiki = Namespace("https://en.wikipedia.org/wiki/")
        self.graph.bind("wiki", self.wiki)
        if cities is not None:
            self.add_cities(cities)

    def add_cities(self, cities: list[City]):
        for city in cities:
            if type(city.wiki_url) == str:
                city.wiki_url = [city.wiki_url]
            for url in city.wiki_url:
                self._add_city(url, city.name, city.country, city.wiki_url, city.ref)
                for twin in city.twin_cities:
                    self._add_twin(url, twin)

    def _add_city(self, url: str, name: str, country: str, same_as: list[str], references: list[Reference] | Reference | None):
        url = URIRef(url)
        self._add_triple(url, RDF.type, self.twin_cities.City)
        self._add_triple(url, RDFS.label, Literal(name))
        self._add_triple(url, self.twin_cities.country, Literal(country))
        for same_as_url in same_as:
            same_as_url = URIRef(same_as_url)
            if same_as_url != url:
                # todo: check if should be bidirectional
                self._add_triple(url, self.twin_cities.sameAs, same_as_url)
        if references is not None:
            if type(references) == Reference:
                references = [references]
            for reference in references:
                self._add_reference(url, reference)

    def _add_twin(self, city_url: str, twin: TwinCitiesAgreement):
        city_url = URIRef(city_url)
        if type(twin.wiki_url) == str:
            twin.wiki_url = [twin.wiki_url]
        for twin_url in twin.wiki_url:
            self._add_city(twin_url, twin.second_city, twin.second_country, twin.wiki_url, twin.ref)
            twin_url = URIRef(twin_url)
            self._add_triple(city_url, self.twin_cities.twin, twin_url)

    def _add_reference(self, city_url: URIRef, reference: Reference):
        if reference.url is None:
            return
        url = URIRef(reference.url)
        self._add_triple(url, RDF.type, self.twin_cities.Reference)
        self._add_triple(url, RDFS.label, Literal(reference.title))
        self._add_triple(url, self.twin_cities.publisher, Literal(reference.publisher))
        self._add_triple(url, self.twin_cities.language, Literal(reference.language))
        self._add_triple(url, self.twin_cities.accessDate, Literal(reference.access_date))
        self._add_triple(url, self.twin_cities.date, Literal(reference.date))

        self._add_triple(city_url, self.twin_cities.reference, url)

    def _add_triple(self, subject: Node | None, predicate: Node, object_: Node | None):
        if subject is None or object_ is None or object_ == Literal("None"):
            return
        if (subject, predicate, object_) not in self.graph:
            self.graph.add((subject, predicate, object_))

    def serialize(self, format_: str = "turtle") -> str:
        return self.graph.serialize(format=format_)

    def save(self, path: str, format_: str = "turtle"):
        self.graph.serialize(destination=path, format=format_)

    def load(self, path: str, format_: str = "turtle"):
        self.graph.parse(path, format=format_)
