import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Tuple

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
    wiki_url: str | List[str]
    ref: List[Reference] | Reference | None


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class City:
    """Class to represent a city"""
    name: str
    country: str
    wiki_url: str
    ref: list[Reference] | None = None
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
        # initial_page = self.get_page("Lists of twin towns and sister cities")
        initial_wiki_text = self.get_wiki_text("Lists of twin towns and sister cities")
        self.add_initial_pages_to_scrape(initial_wiki_text)

        while self.continents_to_scrape:
            title, shown_text = self.continents_to_scrape.pop()
            continent_name = self.get_country_name(shown_text if shown_text != "None" else title)
            wikitext = self.get_wiki_text(title)
            self.scrape_continent(wikitext)

        while self.countries_to_scrape:
            title, shown_text = self.countries_to_scrape.pop()
            country_name = self.get_country_name(shown_text if shown_text != "None" else title)
            wikitext = self.get_wiki_text(title)
            self.scrape_country(wikitext, country_name)

    def scrape_page(self, wikitext: str) -> None:
        """
        Scrape the page
        :param wikitext: Wiki text of the page
        :return: None
        """
        for el in wikitext.nodes:
            if isinstance(el, mwparserfromhell.nodes.tag.Tag):
                if el.tag == 'b':
                    city_page, city_name = el.contents.nodes[0].title, el.contents.nodes[0].text
                if el.tag == 'ref':
                    self.parse_references(el)

    def scrape_continent(self, wikitext: mwparserfromhell.wikicode.Wikicode) -> None:
        """
        Scrape the continent
        :param wikitext: Wiki text of the continent page
        :return: None
        """
        reference_dict = self.build_named_reference_dictionary(wikitext)
        country, city = None, None
        for line in str(wikitext).splitlines():
            if re.match(r"==.*==", line):
                country = re.sub(r"=", "", line).strip()
            if re.match(r"'{3}\[{2}.*]{2}'{3}", line):
                if city is not None:
                    self.cities.append(city)
                city = self.parse_city(line, country, reference_dict)
            if line == "*{{div col end}}":
                continue
            if re.match(r'^\*', line):
                if city is None:
                    city = City(country, country, self.get_url(country))
                twin_city = self.parse_twin_city(line, reference_dict)
                city.twin_cities.append(twin_city)
            if re.match(r"\{\{.*}}", line):
                countries = self.parse_multiple_countries_references(line)
                self.countries_to_scrape.update(countries)

    def scrape_country(self, wikitext: mwparserfromhell.wikicode.Wikicode, country: str) -> None:
        """
        Scrape the country
        :param wikitext: wiki_text of the country page
        :param country: country of the scraped page
        :return: None
        """

        reference_dict = self.build_named_reference_dictionary(wikitext)
        city = None
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

    @staticmethod
    def parse_reference(reference_txt: mwparserfromhell.nodes.template.Template) -> Reference:
        """
        Parse the reference
        :param reference_txt: The reference text
        :return: The reference
        """
        url = reference_txt.get("url").value if reference_txt.has("url") else None
        title = reference_txt.get("title").value if reference_txt.has("title") else None
        publisher = reference_txt.get("publisher").value if reference_txt.has("publisher") else None
        language = reference_txt.get("language").value if reference_txt.has("language") else None
        access_date = reference_txt.get("access-date").value if reference_txt.has("access-date") else None
        date = reference_txt.get("date").value if reference_txt.has("date") else None
        website = reference_txt.get("website").value if reference_txt.has("website") else None
        return Reference(url, website, title, publisher, language, access_date, date)

    @staticmethod
    def parse_value(txt: str) -> str:
        res = txt.split("=")[1]
        res.strip("{}")
        return res

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
        city_refs = [self.parse_reference(ref_match) for ref_match in ref_matches] if ref_matches else None
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
        references = [self.parse_reference(ref_match) for ref_match in ref_matches.groups()] if ref_matches else None
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

    def parse_multiple_city_references(self, city) -> Tuple[str, List[str] | str]:
        """
        Parse the multiple city references
        :param city: The city to parse in the format [[city1|city2|...|cityN]]
        :return: The city and the city url or the cities and the cities url
        """
        city_split = city.split("|")
        if len(city_split) == 1:
            city = city_split[0]
            city_url = self.get_url(city)
        else:
            city_tmp = city_split[0]
            if "," in city_tmp:
                city = city_tmp.split(",")[0]
            else:
                city = city_tmp
            city_url = [self.get_url(tmp) for tmp in city_split]
        return city, city_url

    @staticmethod
    def parse_multiple_countries_references(countries) -> str | List[str]:
        """
        Parse the multiple countries references
        :param countries: The countries to parse in the format {{country1|country2|...|countryN}}
        :return: The countries
        """
        if re.search(r"main", countries, re.IGNORECASE) is None:
            return []
        countries_split = re.sub(r"\{\{|}}", "", countries).split("|")
        if len(countries_split) == 1:
            countries = countries_split[0]
        else:
            countries = [country.strip() for country in countries_split if
                         re.search(r"main", country, re.IGNORECASE) is None]
        return countries

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
                reference_dict[name] = self.parse_reference(template)
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


if __name__ == '__main__':
    main()
    # scraper = Scraper()
    # wiki_text = scraper.get_wiki_text(scraper.get_page("List_of_twin_towns_and_sister_cities_in_Argentina"))
    # scraper.scrape_country(wiki_text, "Argentina")
    # print(scraper.cities)
