import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
import uuid


def run_query(
    sparql: SPARQLWrapper, query: str, city_url: str, cache: bool = False
) -> list[dict[str, str]]:
    """
    Executes a SPARQL query on a given SPARQL endpoint and returns the results as a list of dicts.

    Parameters
    ----------
    sparql : SPARQLWrapper
        The SPARQL endpoint to run the query on.
    query : str
        The SPARQL query to execute.
    city_url : str
        The city URL to replace in the query.

    Returns
    -------
    pd.DataFrame
        The results of the query as a pandas DataFrame.

    Examples
    --------
    >>> sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    >>> query = "SELECT * WHERE { ?id ^schema:about {{CITY_URL}} . }"
    >>> city_url = "https://en.wikipedia.org/wiki/Radom"
    >>> df = run_query(sparql, query, city_url)
    """
    if not cache:
        query = f"#{uuid.uuid4()}\n{query}"
        sparql.addCustomHttpHeader("Cache-Control", "no-cache")
    sparql.setQuery(query.replace("{{CITY_URL}}", str(city_url)))
    ret = sparql.queryAndConvert()
    result = []
    for r in ret["results"]["bindings"]:
        res = {}
        for k in r:
            res[k] = r[k]["value"]
        result.append(res)
    return result


def get_wikidata_twin_data(
    city_url: str, endpoint_url: str = "https://query.wikidata.org/sparql"
) -> list[dict[str, str]]:
    """
    Sets up a SPARQL endpoint for Wikidata, runs a predefined query on it, and returns the results as a list of dicts.

    Parameters
    ----------
    city_url : str
        The city URL to replace in the query.
    endpoint_url : str, optional
        The SPARQL endpoint URL to run the query on. Defaults to "https://query.wikidata.org/sparql".

    Returns
    -------
    pd.DataFrame
        The results of the query as a pandas DataFrame.

    Examples
    --------
    >>> city_url = "https://en.wikipedia.org/wiki/Radom"
    >>> df = get_wikidata_twin_data(city_url)
    """
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setReturnFormat(JSON)

    query = """
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

PREFIX pr: <http://www.wikidata.org/prop/reference/>

PREFIX schema: <http://schema.org/>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ("{{CITY_URL}}" as ?sourceUrl) 
?sourceId ?targetId ?targetUrl ?targetLabel ?starttime ?endtime ?retrieved ?referenceUrl ?referencePublisher ?referenceName
WHERE
{
  {
    ?sourceId ^schema:about <{{CITY_URL}}> .
  }
  ?sourceId p:P190 ?statement.
  ?statement ps:P190 ?targetId.

  OPTIONAL {
    ?targetId ^schema:about ?targetUrl .
    FILTER (REGEX (STR(?targetUrl), "://en.wikipedia"))
  }

  # rank - doesn't matter much - 3 possible values irrelevant for us
  #?statement wikibase:rank ?rank.
  # qualifiers
  OPTIONAL { ?statement pq:P580 ?starttime. }
  OPTIONAL { ?statement pq:P582 ?endtime. }
  # references
  OPTIONAL {
    ?statement prov:wasDerivedFrom ?refnode .
    ?refnode pr:P813 ?retrieved .
  }
  OPTIONAL {
    ?statement prov:wasDerivedFrom ?refnode .
    ?refnode pr:P854 ?referenceUrl .
  }
  OPTIONAL {
    ?statement prov:wasDerivedFrom ?refnode .
    ?refnode pr:P123 ?referencePublisher .
  }
  OPTIONAL {
    ?statement prov:wasDerivedFrom ?refnode .
    ?refnode pr:P1476 ?referenceName .
  }
  SERVICE wikibase:label { 
    bd:serviceParam wikibase:language "en". 
    ?targetId rdfs:label ?targetLabel .
    # ?ref rdfs:label ?labelRef . # refs (retrieved, referenceUrl, referencePublisher, referenceName) labels may be needed in the future
  }
}
    """

    return run_query(sparql, query, city_url)


def extract_id_from_url(
    city_url: str, endpoint_url: str = "https://query.wikidata.org/sparql"
) -> list[str]:
    """
    Extracts the city ID from a given city URL.

    Parameters
    ----------
    city_url : str
        The city URL to extract the city ID from.

    Returns
    -------
    str
        The extracted city ID.

    Examples
    --------
    >>> city_url = "https://en.wikipedia.org/wiki/Radom"
    >>> city_id = extract_id_from_url(city_url)
    """

    query = """
    SELECT ?id
    WHERE
    {
      ?id ^schema:about <{{CITY_URL}}> .
    }
    """
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setReturnFormat(JSON)

    results = run_query(sparql=sparql, query=query, city_url=city_url)
    return [item["id"].split("/")[-1] for item in results]


# def load_wikipedia_graph(filename: str) -> Graph:
#     """
#     Loads a graph from a file.
#
#     Parameters
#     ----------
#     filename : str
#         The filename to load the graph from.
#
#     Returns
#     -------
#     Graph
#         The loaded graph.
#
#     Examples
#     --------
#     >>> graph = load_wikipedia_graph("radom.ttl")
#     """
#     graph = Graph()
#     graph.parse(filename, format="turtle")
#     return graph
#
# def run_wikipedia_query(graph: Graph, query) -> pd.DataFrame:
#     """
#     Runs a predefined query on a given graph and returns the results as a pandas DataFrame.
#
#     Parameters
#     ----------
#     graph : Graph
#     The graph to run the query on.
#     query : str
#     The SPARQL query to execute.
#
#     Returns
#     -------
#     pd.DataFrame
#     The results of the query as a pandas DataFrame.
#
#     Examples
#     --------
#     >>> graph = load_wikipedia_graph("radom.ttl")
#     >>> query = "SELECT * WHERE { ?id ^schema:about {{CITY_URL}} . }"
#     >>> df = run_wikipedia_query(graph, query, city_url)
#     """
#     results = graph.query(query)
#     # df = pd.DataFrame(results.bindings)
#     # df = pd.DataFrame(results.bindings)
#     # df.columns = [str(var) for var in results.vars]
#     # return df
#     return pd.DataFrame(
#         data=([None if x is None else x.toPython() for x in row] for row in results),
#         columns=[str(x) for x in results.vars],
#     )
#
# def get_available_cities_urls(graph: Graph) -> pd.DataFrame:
#     """
#     Retrieves the available city URLs, names, and countries from the given graph.
#
#     Parameters
#     ----------
#     graph : Graph
#         The graph to retrieve the city information from.
#
#     Returns
#     -------
#     pd.DataFrame
#         The city URLs, names, and countries as a pandas DataFrame.
#
#     Examples
#     --------
#     >>> graph = load_wikipedia_graph("twin_cities.ttl")
#     >>> df = get_available_cities_urls(graph)
#     >>> print(df)
#     """
#     df = run_wikipedia_query(
#         graph,
#         """
#         SELECT DISTINCT ?city_url ?city_name ?city_country
#         WHERE {
#             ?city_url a twin-cities:City ;
#                 rdfs:label ?city_name ;
#                 twin-cities:country ?city_country .
#         }
#         order by ?city_url
#         """
#     )
#
#     return df

# graph = load_wikipedia_graph("../twin_cities.ttl")
#         # "sourceWikipediaURL",
#         # "sourceId",
#         # "targetId",
#         # "targetLabel",
#         # "starttime",
#         # "endtime",
#         # "retrieved",
#         # "referenceURL",
#         # "publisher",
#         # "title",
# df = run_wikipedia_query(
#     graph,
#     """
#     SELECT DISTINCT ?city_url ?city_name ?city_country
#     WHERE {
#         ?city_url a twin-cities:City ;
#             rdfs:label ?city_name ;
#             twin-cities:country ?city_country .
#     }
#     order by ?city_url
#     """
# )
# print(df)
# df = get_available_cities_urls(graph)
# print(df)

# df = run_wikidata_query("https://en.wikipedia.org/wiki/Radom")
# print(df)
# df.to_csv("radom.csv", index=False)

# TODO: add more queries from wikipedia graph that will be needed in application
# TODO: diff representation
