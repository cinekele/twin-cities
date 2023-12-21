import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict

import mwparserfromhell
import pywikibot
import selectolax.parser


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class Reference:
    """Class to represent a reference"""
    url: str | None
    website: str | None
    title: str
    publisher: str | None
    language: str | None
    access_date: str | None
    date: str | None


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class TwinCitiesAgreement:
    """Class to represent a twin cities agreement"""
    second_city: str
    second_country: str
    wiki_url: str
    wiki_text: str
    refs: List[Reference] = field(default_factory=list)


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
    twin_cities: List[TwinCitiesAgreement] = field(default_factory=list)


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
        :type page: selectolax.parser.HTMLParser
        :return: The wiki text
        """
        page = pywikibot.Page(self.BASE_SITE, title)
        wiki_text = page.get()
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
            if type(node) == mwparserfromhell.nodes.wikilink.Wikilink and str(node.title).startswith(
                    "List of "):
                if counter == 1:
                    self.continents_to_scrape.add((str(node.title), str(node.text)))
                else:
                    self.countries_to_scrape.add((str(node.title), str(node.text)))
                counter = 0
            elif type(node) == mwparserfromhell.nodes.tag.Tag:
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
            continent_name = self.get_country_name(shown_text if shown_text != "None" else title)
            wikitext = self.get_wiki_text(title)
            cities = self.scrape_continent(wikitext)
            for city in cities:
                city.source_page = title
                city.source_type = "continent"
            self.cities.extend(cities)

        while self.countries_to_scrape:
            title, shown_text = self.countries_to_scrape.pop()
            country_name = self.get_country_name(shown_text if shown_text != "None" else title)
            wikitext = self.get_wiki_text(title)
            self.scrape_country(wikitext, country_name)
            for city in self.cities:
                city.source_page = title
                city.source_type = "country"
            self.cities.extend(self.cities)

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

    def scrape_country(self, wikitext: mwparserfromhell.wikicode.Wikicode, country: str) -> List[City]:
        """
        Scrape the country
        :param wikitext: wiki_text of the country page
        :param country: country of the scraped page
        :return: None
        """

        reference_dict = self.build_named_reference_dictionary(wikitext)
        cities = []
        for line in str(wikitext).splitlines():
            if re.match(r"'{3}\[{2}.*]{2}'{3}", line):
                if city is not None:
                    self.cities.append(city)
                city = self.parse_city(line, country, reference_dict)
            if line == "*{{div col end}}":
                continue
            if re.match(r"^\*", line):
                if city is None:
                    city = City(country, country, self.get_url(country))
                twin_city = self.parse_twin_city(line, reference_dict)
                city.twin_cities.append(twin_city)
            if line == "==External links==":
                break
        return cities

    def parse_reference(self, reference_tag: mwparserfromhell.nodes.tag.Tag,
                        reference_dict: Dict[str, Reference]) -> Reference:
        """
        Parse the reference
        :param reference_dict: Dictionary of the references
        :param reference_tag: The tag of the reference
        :return: The reference
        """
        if len(reference_tag.attributes) == 0:
            reference = self.get_reference(reference_tag.contents.nodes[0])
        else:
            attributes = reference_tag.attributes
            for attribute in attributes:
                if attribute.name == "name":
                    name = str(attribute.value)
            reference = reference_dict[name]
        return reference

    @staticmethod
    def get_reference(reference_txt: mwparserfromhell.nodes.template.Template) -> Reference:
        """
        Parse the reference
        :param reference_txt: The template of the reference
        :return: The reference
        """
        url = str(reference_txt.get("url").value) if reference_txt.has("url") else None
        title = str(reference_txt.get("title").value) if reference_txt.has("title") else None
        publisher = str(reference_txt.get("publisher").value) if reference_txt.has("publisher") else None
        language = str(reference_txt.get("language").value) if reference_txt.has("language") else None
        access_date = str(reference_txt.get("access-date").value) if reference_txt.has("access-date") else None
        date = str(reference_txt.get("date").value) if reference_txt.has("date") else None
        website = str(reference_txt.get("website").value) if reference_txt.has("website") else None
        return Reference(url, website, title, publisher, language, access_date, date)

    def parse_city(self, line: str, country: str, reference_dictionary: dict) -> City:
        """
        Parse the city
        :param reference_dictionary: reference dictionary for the parsed page
        :param line: line of the wiki text
        :param country: country of the city
        :return: City instance
        """
        city = re.search(r"'{3}\[{2}(.*)]{2}'{3}", line).group(0).strip("'[]'")
        city, city_url = self.parse_multiple_city_references(city)
        ref_matches = re.findall(r'<ref>(.*)</ref>', line)
        city_refs = [self.get_reference(ref_match) for ref_match in ref_matches] if ref_matches else None
        named_ref_matches = re.findall(r'(?<=<ref name=).*?(?=/?>)', line)
        named_references = [
            self.parsed_named_references(re.sub(r'["\'\s]+', '', named_ref_match), reference_dictionary) for
            named_ref_match in named_ref_matches
        ] if named_ref_matches else None
        if named_references is not None and city_refs is not None:
            city_refs.extend(named_references)
        elif named_references is not None and city_refs is None:
            city_refs = named_references
        return City(city, country, city_url, city_refs)

    def parse_twin_city(self, line: str, reference_dictionary: dict) -> TwinCitiesAgreement:
        """
        Parse the twin city
        :param reference_dictionary: Reference dictionary for the parsed page
        :param line: line of the wiki text
        :return: TwinCitiesAgreement instance
        """
        twin_city_match = re.search(r'\[{2}(.*)]{2}', line).group(0).strip("[]")
        twin_city, twin_city_url = self.parse_multiple_city_references(twin_city_match)
        country_match = re.search(r'(?<=]]),\s+.*(<ref.*>)?', line)
        country = re.sub(r',\s+|<ref.*>', "", country_match.group(0)) if country_match else None
        ref_matches = re.search(r'<ref>(.*)</ref>', line)
        references = [self.get_reference(ref_match) for ref_match in ref_matches.groups()] if ref_matches else None
        named_ref_matches = re.findall(r'(?<=<ref name=).*?(?=/?>)', line)
        named_references = [
            self.parsed_named_references(re.sub(r'["\'\s]+', '', named_ref_match), reference_dictionary) for
            named_ref_match in
            named_ref_matches] if named_ref_matches else None
        if named_references is not None and references is not None:
            references.extend(named_references)
        elif named_references is not None and references is None:
            references = named_references
        return TwinCitiesAgreement(twin_city, country, twin_city_url, references)

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

    def build_named_reference_dictionary(self, wiki_text: mwparserfromhell.wikicode.Wikicode) -> dict:
        """
        Build the reference dictionary
        :param wiki_text: The wiki text to parse
        :return: The reference dictionary
        """
        reference_dict = {}
        for el in wiki_text.filter(matches=lambda x: isinstance(x, mwparserfromhell.nodes.tag.Tag) and x.tag == 'ref'):
            if len(el.attributes) == 0:
                continue
            for attribute in el.attributes:
                if attribute.name == "name":
                    name = str(attribute.value)
            if len(el.contents.nodes) > 0:
                template = el.contents.nodes[0]
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

    # def parse_reference(self, el: Wikicode) -> Reference:
    #     """
    #     Parse the references
    #     :param el: Wikicode of the reference
    #     :return: Reference
    #     """
    #     elements = el.contents.nodes
    #     for element in elements:
    #         if isinstance(element, mwparserfromhell.nodes.tag.Tag):
    #             if element.tag == 'ref':
    #                 return self.parse_reference(element)


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


if __name__ == '__main__':
    main()
    # continent_test()
    # scraper = Scraper()
    # wiki_text = scraper.get_wiki_text(scraper.get_page("List_of_twin_towns_and_sister_cities_in_Argentina"))
    # scraper.scrape_country(wiki_text, "Argentina")
    # print(scraper.cities)
