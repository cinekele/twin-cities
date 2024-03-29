import os
from datetime import datetime

from dotenv import load_dotenv
from wikidataintegrator import wdi_core, wdi_login, wdi_helpers
from wikidataintegrator.wdi_core import WDTime, WDUrl, WDMonolingualText, WDString

from .queries import extract_id_from_url


class Publisher:
    __slots__ = ["login", "PROPS"]

    def __init__(self):
        """
        Initialize the publisher. Sets up the login.
        """
        load_dotenv()
        login = wdi_login.WDLogin(user=os.getenv("USER"), pwd=os.getenv("PASSWORD"))
        self.PROPS = {
            "retrieved": "P813",
            # "publisher": "P123",
            "title": "P1476",
            "referenceURL": "P854",
            "twin_city": "P190",
        }
        self.login = login

    def load(self, identifier: str) -> wdi_core.WDItemEngine:
        """
        Loads an item from Wikidata.

        Parameters
        ----------
        identifier : str
            The identifier..

        Returns
        -------
        WDItemEngine
            The loaded item.

        Examples
        --------
        >>> publisher = Publisher()
        >>> item = publisher.load("Q104740")
        """

        item = wdi_core.WDItemEngine(wd_item_id=identifier)
        return item

    def _parse_date(self, date_string: str) -> wdi_core.WDTime:
        """
        Loads an item from Wikidata.

        Parameters
        ----------
        date_string : str
            The city URL to replace in the query.

        Returns
        -------
        WDItemEngine
            The loaded item.

        Examples
        --------
        """

        def convert_string_to_date(date_string):
            for fmt in ("%d %B %Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_string.strip(), fmt)
                except ValueError:
                    pass
            raise ValueError("No valid date format found")

        dates = [
            convert_string_to_date(date_string)
            for date_string in date_string.split(" ")
        ]
        date = max(dates)
        date_iso = date.strftime("+%Y-%m-%dT%H:%M:%SZ")

        return wdi_core.WDTime(
            time=date_iso,
            prop_nr=self.PROPS["retrieved"],
            precision=11,
            is_reference=True,
        )

    def _create_reference(
        self, data: dict
    ) -> list[WDTime | WDUrl | WDMonolingualText | WDString]:
        """
        Creates a reference for a given item.

        Parameters
        ----------
        data : dict[str, str]
            The data to create the reference for.

        Returns
        -------
        list[WDTime | WDUrl | WDMonolingualText | WDString]
            The reference.

        Examples
        --------
        """

        reference = []
        if access_data := data.get("accessDate"):
            reference.append(self._parse_date(access_data))
        if referenceURL := data.get("url"):
            reference.append(
                wdi_core.WDUrl(
                    value=referenceURL,
                    prop_nr=self.PROPS["referenceURL"],
                    is_reference=True,
                )
            )
        if title := data.get("name"):
            lang = data.get("language", "en") or "en"
            reference.append(
                wdi_core.WDMonolingualText(
                    value=title,
                    prop_nr=self.PROPS["title"],
                    is_reference=True,
                    language=lang,
                )
            )
        return reference

    def _update(self, item: wdi_core.WDItemEngine, data: dict) -> None:
        twin = data["twin"]
        target_id = data["targetId"]
        references = [self._create_reference(ref) for ref in twin["references"]]
        twin_city = wdi_core.WDItemID(
            value=target_id, prop_nr=self.PROPS["twin_city"], references=references
        )
        new_item = wdi_core.WDItemEngine(data=[twin_city], wd_item_id=item.wd_item_id)
        result = wdi_helpers.try_write(
            new_item,
            item.wd_item_id,
            record_prop=self.PROPS["twin_city"],
            login=self.login,
            edit_summary=f"Added twin city {twin['name']}",
        )
        if isinstance(result, Exception):
            raise Exception(result.wd_error_msg["error"]["info"])
        return result

    def get_proper_id(self, url: str) -> str:
        ids = extract_id_from_url(url)
        if len(ids) == 0:
            raise Exception("ID in Wikidata not found")
        return ids[0]

    def update(self, data: dict, two_sided: bool = True) -> bool:
        source_id = data.get("sourceId")
        source_id = (
            source_id.split("/")[-1]
            if source_id is not None
            else self.get_proper_id(data["sourceUrl"])
        )
        target_id = self.get_proper_id(data["twin"]["url"])
        data["targetId"] = target_id
        item = self.load(source_id)
        self._update(item, data)
        if two_sided:
            data["targetId"] = source_id
            data["twin"]["name"] = item.get_label()
            item = self.load(target_id)
            self._update(item, data)
        return True


if __name__ == "__main__":
    publisher = Publisher()
    data = {
        "sourceUrl": "https://en.wikipedia.org/wiki/Marzahn-Hellersdorf",
        "twin": {
            "url": "https://en.wikipedia.org/wiki/Tychy",
            "name": "Tychy",
            "country": "Poland",
            "sourcePage": "List of twin towns and sister cities in Poland",
            "sourceType": "country",
            "wikiText": "Tychy",
            "references": [
                {
                    "name": "Miasta partnerskie",
                    "url": "https://umtychy.pl/artykul/108/miasta-partnerskie",
                    "publisher": "Tychy",
                    "language": "pl",
                    "accessDate": "2019-09-21",
                    "date": None,
                }
            ],
        },
    }

    publisher.update(data)
