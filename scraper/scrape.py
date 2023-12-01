import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Tuple
import json

import httpx
import selectolax.parser


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class Reference:
    """Class to represent a reference"""
    url: str | None
    title: str
    publisher: str | None
    language: str | None
    access_date: str | None
    date: str | None


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class TwinCitiesAgreement:
    """Class to represent a twin cities agreement"""
    second_city: str
    second_country: str | None
    wiki_url: str | List[str]
    ref: List[Reference] | Reference | None


@dataclass(init=True, repr=True, eq=True, order=True, unsafe_hash=False, frozen=False, slots=True)
class City:
    """Class to represent a city"""
    name: str
    country: str
    wiki_url: str | List[str]
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
        self.HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/119.0.0.0 Safari/537.36"
        }
        self.countries_to_scrape = set()
        self.continents_to_scrape = set()
        self.cities = []

    def get_page(self, title: str) -> selectolax.parser.HTMLParser | bool:
        """
        Get the page from the url
        :param title: The title of the wiki page
        :type title: str
        :return: The page parsed with the Selectolax parser or False if there was an error
        """
        url = self.url_edit(title)
        page = httpx.get(url, headers=self.HEADERS, follow_redirects=True)
        try:
            page.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(f"HTTP Error: {exc}")
            return False
        selectolax_page = selectolax.parser.HTMLParser(page.text)
        return selectolax_page

    def url_edit(self, title: str) -> str:
        """
        Join the url with the base path
        :param title: The title to join
        :type title: str
        :return: The joined url
        """
        title_url_part = re.sub(r"\s+", "_", title)
        return self.BASE_PATH + "w/index.php?title=" + title_url_part + "&action=edit"

    def url_get(self, title: str) -> str:
        """
        Join the url with the base path
        :param title: The title to join
        :type title: str
        :return: The joined url
        """
        title_url_part = re.sub(r"\s+", "_", title)
        return self.BASE_PATH + "wiki/" + title_url_part

    @staticmethod
    def get_wiki_text(page: selectolax.parser.HTMLParser) -> str:
        """
        Get the wiki text from the page
        :param page: The page to get the wiki text from
        :type page: selectolax.parser.HTMLParser
        :return: The wiki text
        """
        wiki_text = page.css_first("textarea#wpTextbox1").text()
        return wiki_text

    def add_initial_pages_to_scrape(self, wiki_text: str) -> None:
        """
        Add the pages to the scraper
        :param wiki_text: Wiki text of the initial page
        :type wiki_text: str
        :return: None
        """
        for line in wiki_text.splitlines():
            if re.match(r"\*\s+", line):
                continent = re.sub(r"[*\[\]]", "", line).strip()
                split_continent = continent.split("|")
                self.continents_to_scrape.update(split_continent)
            if re.match(r"\*{2}\s+", line):
                country = re.sub(r"[*\[\]]", "", line).strip()
                split_country = country.split("|")
                self.countries_to_scrape.update(split_country)

    def run(self) -> None:
        """
        Run the scraper
        :return: None
        """
        initial_page = self.get_page("Lists of twin towns and sister cities")
        initial_wiki_text = self.get_wiki_text(initial_page)
        if initial_page:
            self.add_initial_pages_to_scrape(initial_wiki_text)
        else:
            raise Exception("Error getting the initial page")

        while self.continents_to_scrape:
            page = self.get_page(self.continents_to_scrape.pop())
            if page:
                wiki_text = self.get_wiki_text(page)
                self.scrape_continent(wiki_text)

        while self.countries_to_scrape:
            country_list = self.countries_to_scrape.pop()
            page = self.get_page(country_list)
            if page:
                wiki_text = self.get_wiki_text(page)
                country_name = self.get_country_name(country_list)
                self.scrape_country(wiki_text, country_name)

    def scrape_continent(self, wiki_text: str) -> None:
        """
        Scrape the continent
        :param wiki_text: Wiki text of the continent page
        :return: None
        """
        if not self.is_redirect_page(wiki_text):
            return

        reference_dict = self.build_named_reference_dictionary(wiki_text)
        country, city = None, None
        for line in wiki_text.splitlines():
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
                    city = City(country, country, self.url_get(country))
                twin_city = self.parse_twin_city(line, reference_dict)
                city.twin_cities.append(twin_city)
            if re.match(r"\{\{.*}}", line):
                countries = self.parse_multiple_countries_references(line)
                self.countries_to_scrape.update(countries)

    def scrape_country(self, wiki_text: str, country: str) -> None:
        """
        Scrape the country
        :param wiki_text: wiki_text of the country page
        :param country: country of the scraped page
        :return: None
        """
        if not self.is_redirect_page(wiki_text):
            return

        reference_dict = self.build_named_reference_dictionary(wiki_text)
        city = None
        for line in wiki_text.splitlines():
            if re.match(r"'{3}\[{2}.*]{2}'{3}", line):
                if city is not None:
                    ## This way we don't have to wait for all the results to preview what we have
                    ## (also we can see some results in case of error, e.g. timeout)
                    # mode = "a" if os.path.exists("test.jsonl") else "w"
                    # with open("test.jsonl", mode, encoding="utf-8") as f:
                    #     f.write(json.dumps(asdict(city)) + "\n")
                    self.cities.append(city)
                city = self.parse_city(line, country, reference_dict)
            if line == "*{{div col end}}":
                continue
            if re.match(r"^\*", line):
                if city is None:
                    city = City(country, country, self.url_get(country))
                twin_city = self.parse_twin_city(line, reference_dict)
                city.twin_cities.append(twin_city)
            if line == "==External links==":
                break

    @staticmethod
    def is_redirect_page(wiki_text: str) -> bool:
        """
        Check if the page is a redirect page
        :param wiki_text: wiki_text of the page
        :return: True if the page is a redirect page, False otherwise
        """
        return re.match(r"#REDIRECT", wiki_text) is None

    @staticmethod
    def parse_reference(reference_txt: str) -> Reference:
        """
        Parse the reference
        :param reference_txt: The reference text
        :return: The reference
        """
        strip_text = re.sub(r"<ref name=\w*>|<ref>|\{\{|</ref>|}}", "", reference_txt)
        url, title, publisher, language, access_date, date = 6 * (None,)
        for txt in strip_text.split("|"):
            if txt.startswith("url="):
                url = txt.split("=")[1]
            if txt.startswith("title="):
                title = txt.split("=")[1]
            if txt.startswith("publisher="):
                publisher = txt.split("=")[1]
            if txt.startswith("language="):
                language = txt.split("=")[1]
            if txt.startswith("date="):
                date = txt.split("=")[1]
            if txt.startswith("access-date="):
                access_date = txt.split("=")[1]
        return Reference(url, title, publisher, language, access_date, date)

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
            city_url = self.url_get(city)
        else:
            city_tmp = city_split[0]
            if "," in city_tmp:
                city = city_tmp.split(",")[0]
            else:
                city = city_tmp
            city_url = [self.url_get(tmp) for tmp in city_split]
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

    def build_named_reference_dictionary(self, wiki_text: str) -> dict:
        """
        Build the reference dictionary
        :param wiki_text: The wiki text to parse
        :return: The reference dictionary
        """
        reference_dict = {}
        find_references = re.findall(r"<ref name=[^>]+?>\{\{.+?}}</ref>", wiki_text)
        for found_reference in find_references:
            ref_name = re.search(r"(?<=name=).*?(?=>)", found_reference).group(0)
            clean_ref_name = re.sub(r'["\'\s]+', '', ref_name)
            reference = self.parse_reference(found_reference)
            reference_dict[clean_ref_name] = reference
        return reference_dict

    def save_cities(self, filename: str = "cities.jsonl"):
        """
        Save the cities in a file
        :return: None
        """
        with open(filename, "w", encoding="utf-8") as f:
            for city in self.cities:
                f.write(json.dumps(asdict(city)) + "\n")

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


if __name__ == '__main__':
    scraper = Scraper()
    import time
    start_time = time.time()
    scraper.run()
    print(f"--- {time.time() - start_time:.2f} seconds ---")
    # print(scraper.cities)
    scraper.save_cities()
