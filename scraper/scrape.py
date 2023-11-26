import re
from dataclasses import dataclass, field
from typing import List, Tuple

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

        country, city = None, None
        for line in wiki_text.splitlines():
            if re.match(r"==.*==", line):
                country = re.sub(r"=", "", line).strip()
            if re.match(r"'{3}\[{2}.*]{2}'{3}", line):
                if city is not None:
                    self.cities.append(city)
                city = self.parse_city(line, country)
            if re.match(r'^\*', line):
                if city is None:
                    city = City(country, country, self.url_get(country))
                twin_city = self.parse_twin_city(line)
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

        city = None
        for line in wiki_text.splitlines():
            if re.match(r"'{3}\[{2}.*]{2}'{3}", line):
                if city is not None:
                    self.cities.append(city)
                city = self.parse_city(line, country)
            if re.match(r'^\*\[\[', line):
                if city is None:
                    city = City(country, country, self.url_get(country))
                twin_city = self.parse_twin_city(line)
                city.twin_cities.append(twin_city)

    @staticmethod
    def is_redirect_page(wiki_text: str) -> bool:
        """
        Check if the page is a redirect page
        :param wiki_text: wiki_text of the page
        :return: True if the page is a redirect page, False otherwise
        """
        return re.match(r"#REDIRECT", wiki_text) is None

    def parse_reference(self, reference_txt: str) -> Reference:
        """
        Parse the reference
        :param reference_txt: The reference text
        :return: The reference
        """
        strip_text = re.sub(r"<ref.*>|\{\{|</ref>|}}", "", reference_txt)
        url, title, publisher, language, access_date = None, None, None, None, None
        for txt in strip_text.split("|"):
            if txt.startswith("url="):
                url = txt.split("=")[1]
            if txt.startswith("title="):
                title = txt.split("=")[1]
            if txt.startswith("publisher="):
                publisher = txt.split("=")[1]
            if txt.startswith("language="):
                language = txt.split("=")[1]
            if txt.startswith("access-date="):
                access_date = txt.split("=")[1]
        return Reference(url, title, publisher, language, access_date)

    def parse_city(self, line, country) -> City:
        """
        Parse the city
        :param line: line of the wiki text
        :param country: country of the city
        :return: City instance
        """
        city = re.search(r'\[{2}(.*)]{2}', line).group(0).strip("[]")
        city, city_url = self.parse_multiple_city_references(city)
        ref_matches = re.search(r'<ref>(.*)</ref>', line)
        city_refs = [self.parse_reference(ref_match) for ref_match in ref_matches.groups()] if ref_matches else None
        return City(city, country, city_url, city_refs)

    def parse_twin_city(self, line) -> TwinCitiesAgreement:
        """
        Parse the twin city
        :param line: line of the wiki text
        :return: TwinCitiesAgreement instance
        """
        twin_city_match = re.search(r'\[{2}(.*)]{2}', line).group(0).strip("[]")
        twin_city, twin_city_url = self.parse_multiple_city_references(twin_city_match)
        country_match = re.search(r'(?<=]]),\s+.*(<ref.*>)?', line)
        country = re.sub(r',\s+|<ref.*>', "", country_match.group(0)) if country_match else None
        ref_matches = re.search(r'<ref>(.*)</ref>', line)
        references = [self.parse_reference(ref_match) for ref_match in ref_matches.groups()] if ref_matches else None
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
            for city_s in city_split:
                city_s = city_s.strip()
                city_s = city_s.split(",")[0]
            city = city_s
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
        country_rep = re.search(r"(?<=(in\s)).+", country_string).group(0)
        country_name = re.sub(r"the", "", country_rep).strip()
        return country_name

    def save_cities(self, filename: str = "cities.jsonl"):
        """
        Save the cities in a file
        :return: None
        """
        with open(filename, "w", encoding="utf-8") as f:
            for city in self.cities:
                f.write(str(city) + "\n")


if __name__ == '__main__':
    scraper = Scraper()
    scraper.run()
    # print(scraper.cities)
    scraper.save_cities()
