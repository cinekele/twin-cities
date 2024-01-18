from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS
from rdflib.term import Node

from scraper.scrape import City, TwinCitiesAgreement, Reference


def coalesce(*arg):
    return next((a for a in arg if a is not None), None)


class TwinCitiesGraph:
    def __init__(self, cities: list[City] = None):
        self.graph = Graph()
        self.twin_cities = Namespace("https://mini.pw.edu.pl/twin-cities#")
        self.graph.bind("twin-cities", self.twin_cities)
        self.wiki = Namespace("https://en.wikipedia.org/wiki/")
        self.graph.bind("wiki", self.wiki)
        self.references = {}
        self.city_pairs = {}

        if cities is not None:
            self.add_cities(cities)

    def add_cities(self, cities: list[City]):
        for city in cities:
            self._add_city(city.wiki_url, city.name, city.country, city.wiki_text, city.source_page, city.source_type)

            for twin in city.twin_cities:
                self._add_twin(city.wiki_url, twin)

                for reference in city.ref:
                    self._add_reference(reference, URIRef(city.wiki_url), URIRef(twin.wiki_url))
                for reference in twin.refs:
                    self._add_reference(reference, URIRef(city.wiki_url), URIRef(twin.wiki_url))

    def _add_city(self, url: str, name: str, country: str, wiki_text: str, source_page: str | None, source_type: str | None):
        url = URIRef(url)
        self._add_triple(url, RDF.type, self.twin_cities.City)
        self._add_triple(url, RDFS.label, Literal(name))
        self._add_triple(url, self.twin_cities.country, Literal(country))
        self._add_triple(url, self.twin_cities.wikiText, Literal(wiki_text))
        self._add_triple(url, self.twin_cities.sourcePage, Literal(source_page))
        self._add_triple(url, self.twin_cities.sourceType, Literal(source_type))

    def _add_twin(self, city_url: str, twin: TwinCitiesAgreement):
        city_url = URIRef(city_url)
        self._add_city(twin.wiki_url, twin.second_city, twin.second_country, twin.wiki_text, None, None)
        twin_url = URIRef(twin.wiki_url)
        self._add_triple(city_url, self.twin_cities.twin, twin_url)
        self._add_triple(twin_url, self.twin_cities.twin, city_url)

    def _add_reference(self, reference: Reference, city_url: URIRef, twin_url: URIRef):
        url = coalesce(reference.url, reference.website, reference.title, reference.publisher, "unknown")

        if url in self.references:
            ref = self.references[url]
        else:
            ref = BNode()
            self._add_triple(ref, RDF.type, self.twin_cities.Reference)
            self._add_triple(ref, self.twin_cities.url, Literal(reference.url))

        self._add_triple(ref, self.twin_cities.website, Literal(reference.website))
        self._add_triple(ref, RDFS.label, Literal(reference.title))
        self._add_triple(ref, self.twin_cities.publisher, Literal(reference.publisher))
        self._add_triple(ref, self.twin_cities.language, Literal(reference.language))
        self._add_triple(ref, self.twin_cities.accessDate, Literal(reference.access_date))
        self._add_triple(ref, self.twin_cities.date, Literal(reference.date))

        if (city_url, twin_url) in self.city_pairs:
            city_pair = self.city_pairs[(city_url, twin_url)]
        elif (twin_url, city_url) in self.city_pairs:
            city_pair = self.city_pairs[(twin_url, city_url)]
        else:
            city_pair = BNode()
            self._add_triple(city_pair, RDF.type, self.twin_cities.CityPair)
            self._add_triple(city_pair, self.twin_cities.city, city_url)
            self._add_triple(city_pair, self.twin_cities.city, twin_url)
        self._add_triple(ref, self.twin_cities.city_pair, city_pair)

        self._add_triple(city_url, self.twin_cities.reference, ref)
        self._add_triple(twin_url, self.twin_cities.reference, ref)

        self.references[url] = ref
        self.city_pairs[(city_url, twin_url)] = city_pair

    def _add_triple(self, subject: Node | None, predicate: Node, object_: Node | None):
        if subject is None or object_ is None or object_ == Literal("None"):
            return
        if (subject, predicate, object_) not in self.graph:
            self.graph.add((subject, predicate, object_))

    def get_cities(self) -> list[dict[str, str]]:
        cities = []
        for city_url in self.graph.subjects(RDF.type, self.twin_cities.City):
            if self.graph.value(city_url, self.twin_cities.twin) is None:
                continue
            city = {
                "url": city_url,
                "name": self.graph.value(city_url, RDFS.label),
                "country": self.graph.value(city_url, self.twin_cities.country)
            }
            for key, value in city.items():
                city[key] = value.toPython() if value is not None else None
            cities.append(city)
        return cities

    def get_twins(self, city_url: str) -> list[dict[str, str]]:
        twins = []
        for twin_url in self.graph.objects(URIRef(city_url), self.twin_cities.twin):
            twin = {
                "url": twin_url,
                "name": self.graph.value(twin_url, RDFS.label),
                "country": self.graph.value(twin_url, self.twin_cities.country),
                "sourcePage": self.graph.value(twin_url, self.twin_cities.sourcePage),
                "sourceType": self.graph.value(twin_url, self.twin_cities.sourceType),
                "wikiText": self.graph.value(twin_url, self.twin_cities.wikiText)
            }
            for key, value in twin.items():
                twin[key] = value.toPython() if value is not None else None
            twins.append(twin)

        return twins

    def get_references(self, city_url: str, twin_url: str) -> list[dict[str, str]]:
        city_url = URIRef(city_url)
        twin_url = URIRef(twin_url)

        refs = []
        for ref_url in list(self.graph.objects(city_url, self.twin_cities.reference)) + \
                       list(self.graph.objects(twin_url, self.twin_cities.reference)):
            if not self._is_reference_relevant(ref_url, city_url, twin_url):
                continue

            url = self.graph.value(ref_url, self.twin_cities.url)
            if url.toPython() in [r["url"] for r in refs]:
                continue

            ref = {
                "name": self.graph.value(ref_url, RDFS.label),
                "url": url,
                "website": self.graph.value(ref_url, self.twin_cities.website),
                "publisher": self.graph.value(ref_url, self.twin_cities.publisher),
                "language": self.graph.value(ref_url, self.twin_cities.language),
                "accessDate": list(self.graph.objects(ref_url, self.twin_cities.accessDate)),
                "date": self.graph.value(ref_url, self.twin_cities.date)
            }
            for key, value in ref.items():
                if key == "accessDate":
                    ref[key] = " ".join([x.toPython() for x in value]) if value is not None else None
                    continue
                ref[key] = value.toPython() if value is not None else None
            refs.append(ref)
        return refs

    def _is_reference_relevant(self, ref_url: Node, city_url: URIRef, twin_url: URIRef) -> bool:
        city_pairs = list(self.graph.objects(ref_url, self.twin_cities.city_pair))
        for city_pair in city_pairs:
            city_pair_cities = list(self.graph.objects(city_pair, self.twin_cities.city))
            if city_url in city_pair_cities and twin_url in city_pair_cities:
                return True
        return False

    def serialize(self, format_: str = "turtle") -> str:
        return self.graph.serialize(format=format_)

    def save(self, path: str, format_: str = "turtle"):
        self.graph.serialize(destination=path, format=format_)

    def load(self, path: str, format_: str = "turtle"):
        self.graph.parse(path, format=format_)
