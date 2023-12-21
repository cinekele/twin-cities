import json
import re
from dataclasses import dataclass, field, asdict

import mwparserfromhell
import pywikibot


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class Reference:
    """Class to represent a reference"""
    url: str | None = None
    website: str | None = None
    title: str | None = None
    publisher: str | None = None
    language: str | None = None
    access_date: str | None = None
    date: str | None = None


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class TwinCitiesAgreement:
    """Class to represent a twin cities agreement"""
    second_city: str
    second_country: str
    wiki_url: str
    wiki_text: str
    refs: list[Reference] = field(default_factory=list)


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class City:
    """Class to represent a city"""
    name: str
    country: str
    wiki_url: str
    wiki_text: str
    source_page: str | None = None
    source_type: str = "country"
    ref: list[Reference] = field(default_factory=list)
    twin_cities: list[TwinCitiesAgreement] = field(default_factory=list)


class Scraper:
    """Class to scrape the data"""

    def __init__(self):
        """
        Initialize the scraper
        :return: The scraper
        """
        self.BASE_PATH = "https://en.wikipedia.org/"
        self.BASE_SITE = pywikibot.Site('en', 'wikipedia')
        self.countries_to_scrape = set()
        self.continents_to_scrape = set()
        self.cities = []

    def get_url(self, title: str) -> str:
        """
        Join the url with the base path
        :param title: The title to join
        :type title: str
        :return: The joined url
        """
        title_url_part = re.sub(r"\s+", "_", title)
        return self.BASE_PATH + "wiki/" + title_url_part

    def get_wiki_text(self, title: str) -> mwparserfromhell.wikicode.Wikicode:
        """
        Get the wiki text from the page
        :param page: The page to get the wiki text from
        :return: The wiki text parsed
        """
        page = pywikibot.Page(self.BASE_SITE, title)
        wiki_text = page.get(get_redirect=True)
        return mwparserfromhell.parse(wiki_text, skip_style_tags=True)

    def add_initial_pages_to_scrape(self, wikitext: mwparserfromhell.wikicode.Wikicode) -> None:
        """
        Add the pages to the scraper
        :param wikitext: Wiki text of the initial page
        :type wikitext: str
        :return: None
        """
        counter = 0
        for node in wikitext.filter(matches=lambda x: isinstance(x, mwparserfromhell.nodes.wikilink.Wikilink) or (
                isinstance(x, mwparserfromhell.nodes.tag.Tag) and x.tag == 'li')):
            if isinstance(node, mwparserfromhell.nodes.wikilink.Wikilink) and str(node.title).startswith(
                    "List of "):
                if counter == 1:
                    self.continents_to_scrape.add((str(node.title), str(node.text) if node.text is not None else None))
                else:
                    self.countries_to_scrape.add((str(node.title), str(node.text) if node.text is not None else None))
                counter = 0
            elif isinstance(node, mwparserfromhell.nodes.tag.Tag):
                counter += 1

    def run(self) -> None:
        """
        Run the scraper
        :return: None
        """
        initial_wiki_text = self.get_wiki_text("Lists of twin towns and sister cities")
        self.add_initial_pages_to_scrape(initial_wiki_text)

        while self.continents_to_scrape:
            title, shown_text = self.continents_to_scrape.pop()
            wikitext = self.get_wiki_text(title)
            cities = self.scrape_continent(wikitext)
            for city in cities:
                city.source_page = title
                city.source_type = "continent"
            self.cities.extend(cities)

        while self.countries_to_scrape:
            title, shown_text = self.countries_to_scrape.pop()
            country_name = self.get_country_name(shown_text if shown_text is not None else title)
            if country_name == "Metro Manila":
                continue
            wikitext = self.get_wiki_text(title)
            cities = self.scrape_country(wikitext, country_name)
            for city in cities:
                city.source_page = title
                city.source_type = "country"
            self.cities.extend(cities)

    def scrape_continent(self, wikitext: mwparserfromhell.wikicode.Wikicode) -> list[City]:
        """
        Scrape the continent
        :param wikitext: Wiki text of the continent page
        :return: parsed cities
        """
        reference_dict = self.build_named_reference_dictionary(wikitext)
        cities = []
        country, city, twin_city, twin_city_ref = 4 * [None]
        count = 0
        last_count = -1
        for line in wikitext.filter(matches=lambda x: isinstance(x, (mwparserfromhell.nodes.template.Template,
                                                                     mwparserfromhell.nodes.tag.Tag,
                                                                     mwparserfromhell.nodes.heading.Heading,
                                                                     mwparserfromhell.wikicode.Wikilink))):
            if isinstance(line, mwparserfromhell.nodes.heading.Heading):
                country = str(line.title)
                if city is not None:
                    count = 0
                    city = None
                    twin_city = None
                if country == "References":
                    break
            elif isinstance(line, mwparserfromhell.wikicode.Wikilink):
                if country is None:
                    continue
                if count == 0 or last_count == count:
                    city_name, city_title = str(line.text if line.text is not None else line.title), str(line.title)
                    city_url = self.get_url(str(line.title))
                    city = City(name=city_name, country=country, wiki_text=city_title, wiki_url=city_url)
                    last_count = -1
                    count = 0
                    cities.append(city)
                else:
                    twin_city_name, twin_city_title = str(line.text if line.text is not None else line.title), str(
                        line.title)
                    twin_city_url = self.get_url(str(line.title))
                    twin_country = wikitext.nodes[wikitext.index(line) + 1].strip(", \n'")
                    twin_city = TwinCitiesAgreement(second_city=twin_city_name, second_country=twin_country,
                                                    wiki_url=twin_city_url,
                                                    wiki_text=twin_city_title)
                    city.twin_cities.append(twin_city)
                    last_count = count
            elif isinstance(line, mwparserfromhell.nodes.tag.Tag) and line.tag == "ref":
                if count == 0:
                    city_ref = self.parse_reference(line, reference_dict)
                    city.ref.append(city_ref)
                else:
                    twin_city_ref = self.parse_reference(line, reference_dict)
                    twin_city.refs.append(twin_city_ref)
            elif isinstance(line, mwparserfromhell.nodes.tag.Tag) and line.tag == "li":
                count += 1
                if city is None:
                    city = City(country, country, wiki_text=country, wiki_url=self.get_url(country))
            elif isinstance(line, mwparserfromhell.nodes.template.Template) and line.name == 'main':
                another_list = line.params[0].value
                self.countries_to_scrape.add((str(another_list), None))
        return cities

    def scrape_country(self, wikitext: mwparserfromhell.wikicode.Wikicode, country: str) -> list[City]:
        """
        Scrape the country
        :param wikitext: wiki_text of the country page
        :param country: country of the scraped page
        :return: None
        """

        reference_dict = self.build_named_reference_dictionary(wikitext)
        cities = []
        header, city, twin_city, twin_city_ref = 4 * [None]
        count = 0
        last_count = -1
        for line in wikitext.filter(matches=lambda x: isinstance(x, (mwparserfromhell.nodes.template.Template,
                                                                     mwparserfromhell.nodes.tag.Tag,
                                                                     mwparserfromhell.nodes.heading.Heading,
                                                                     mwparserfromhell.wikicode.Wikilink))):
            if isinstance(line, mwparserfromhell.nodes.heading.Heading):
                header = str(line.title)
                if city is not None:
                    count = 0
                    city = None
                    twin_city = None
                if header == "References":
                    break
            elif isinstance(line, mwparserfromhell.wikicode.Wikilink):
                if header is None:
                    continue
                if count == 0 or last_count == count:
                    city_name, city_title = str(line.text if line.text is not None else line.title), str(line.title)
                    if city_name == "town twinning" or city_name == "European Union":
                        continue
                    city_url = self.get_url(str(line.title))
                    city = City(name=city_name, country=country, wiki_text=city_title, wiki_url=city_url)
                    last_count = -1
                    count = 0
                    cities.append(city)
                else:
                    twin_city_name, twin_city_title = str(line.text if line.text is not None else line.title), str(
                        line.title)
                    twin_city_url = self.get_url(str(line.title))
                    twin_country = wikitext.nodes[wikitext.index(line) + 1].strip(", \n'")
                    twin_city = TwinCitiesAgreement(second_city=twin_city_name, second_country=twin_country,
                                                    wiki_url=twin_city_url,
                                                    wiki_text=twin_city_title)
                    city.twin_cities.append(twin_city)
                    last_count = count
            elif isinstance(line, mwparserfromhell.nodes.tag.Tag) and line.tag == "ref":
                if header is None:
                    continue
                if count == 0:
                    city_ref = self.parse_reference(line, reference_dict)
                    if city_ref is not None:
                        city.ref.append(city_ref)
                else:
                    twin_city_ref = self.parse_reference(line, reference_dict)
                    if twin_city_ref is not None:
                        twin_city.refs.append(twin_city_ref)
            elif isinstance(line, mwparserfromhell.nodes.tag.Tag) and line.tag == "li":
                count += 1
                if city is None:
                    city = City(country, country, wiki_text=country, wiki_url=self.get_url(country))
            elif isinstance(line, mwparserfromhell.nodes.template.Template) and line.name == 'main':
                another_list = line.params[0].value
                self.countries_to_scrape.add((str(another_list), None))
        return cities

    def parse_reference(self, reference_tag: mwparserfromhell.nodes.tag.Tag,
                        reference_dict: dict[str, Reference]) -> Reference:
        """
        Parse the reference
        :param reference_dict: Dictionary of the references
        :param reference_tag: The tag of the reference
        :return: The reference
        """
        if len(reference_tag.attributes) == 0:
            reference = self.get_reference(reference_tag.contents.nodes)
        else:
            attributes = reference_tag.attributes
            for attribute in attributes:
                if attribute.name == "name":
                    name = str(attribute.value)
            reference = reference_dict[name] if name in reference_dict else None
        return reference

    @staticmethod
    def get_reference(
            nodes: list[mwparserfromhell.nodes.Node]) -> Reference:
        """
        Parse the reference
        :return: The reference
        """
        if len(nodes) == 1:
            reference_txt = nodes[0]
        else:
            if str(nodes[0]).startswith("url"):
                url = str(nodes[1])
                return Reference(url=url)
            else:
                reference_txt = nodes[0]
        if isinstance(reference_txt, mwparserfromhell.nodes.ExternalLink):
            return Reference(url=str(reference_txt.url))
        url = str(reference_txt.get("url").value) if reference_txt.has("url") else None
        title = str(reference_txt.get("title").value) if reference_txt.has("title") else None
        publisher = str(reference_txt.get("publisher").value) if reference_txt.has("publisher") else None
        language = str(reference_txt.get("language").value) if reference_txt.has("language") else None
        access_date = str(reference_txt.get("access-date").value) if reference_txt.has("access-date") else None
        date = str(reference_txt.get("date").value) if reference_txt.has("date") else None
        website = str(reference_txt.get("website").value) if reference_txt.has("website") else None
        return Reference(url, website, title, publisher, language, access_date, date)

    @staticmethod
    def get_country_name(country_string: str) -> str:
        """
        Get the country name
        :param country_string: The country string in the format "List of [...] in [the] country_name"
        :return: The country name
        """
        country_rep = re.search(r"(?<=\sin\s).+", country_string).group(0)
        country_name = country_rep.replace("the ", "")
        return country_name

    def build_named_reference_dictionary(self, wiki_text: mwparserfromhell.wikicode.Wikicode) -> dict[str, Reference]:
        """
        Build the reference dictionary
        :param wiki_text: The wiki text to parse
        :return: The reference dictionary
        """
        reference_dict = {}
        for el in wiki_text.filter(matches=lambda x: isinstance(x, mwparserfromhell.nodes.tag.Tag) and x.tag == 'ref'):
            if len(el.attributes) == 0:
                continue
            is_good = True
            for attribute in el.attributes:
                if attribute.name == "name":
                    name = str(attribute.value)
                if attribute.name == "group":
                    is_good = False
            if len(el.contents.nodes) == 1 and is_good:
                template = el.contents.nodes
                reference_dict[name] = self.get_reference(template)
        return reference_dict

    def save_cities(self, filename: str = "cities.jsonl"):
        """
        Save the cities in a file
        :return: None
        """
        with open(filename, "w", encoding="utf-8") as f:
            for city in self.cities:
                f.write(json.dumps(asdict(city), ensure_ascii=False) + "\n")

    @staticmethod
    def parsed_named_references(named_ref_match: str, reference_dictionary: dict) -> Reference | None:
        """
        Parse the named references
        :param named_ref_match: The named references to parse
        :param reference_dictionary: Reference dictionary
        :return: Reference or None
        """
        if named_ref_match:
            named_ref = reference_dictionary[named_ref_match]
            return named_ref
        return None


def main():
    scraper = Scraper()
    import time
    start_time = time.time()
    scraper.run()
    print(f"--- {time.time() - start_time:.2f} seconds ---")
    scraper.save_cities()


def continent_test():
    scraper = Scraper()
    wiki_text = scraper.get_wiki_text("List of sister cities in Europe")
    result = scraper.scrape_continent(wiki_text)
    for res in result:
        print(res)
        for twin in res.twin_cities:
            print(twin)


def country_test():
    scraper = Scraper()
    wiki_text = scraper.get_wiki_text("List of twin towns and sister cities in Poland")
    result = scraper.scrape_country(wiki_text, "Poland")
    for res in result:
        print(res)
        for twin in res.twin_cities:
            print(twin)


if __name__ == '__main__':
    # country_test()
    # continent_test()
    main()
