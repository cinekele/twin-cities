import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

def run_query(sparql: SPARQLWrapper, query: str, city_url: str) -> pd.DataFrame:
    """
    Executes a SPARQL query on a given SPARQL endpoint and returns the results as a pandas DataFrame.

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
    sparql.setQuery(query.replace("{{CITY_URL}}", str(city_url)))
    ret = sparql.queryAndConvert()
    result = []
    for r in ret["results"]["bindings"]:
        res = {}
        for k in r:
            res[k] = r[k]["value"]
        result.append(res)
    df = pd.DataFrame(result)
    return df

def run_wikidata_query(city_url: str, endpoint_url: str = "https://query.wikidata.org/sparql") -> pd.DataFrame:
    """
    Sets up a SPARQL endpoint for Wikidata, runs a predefined query on it, and returns the results as a pandas DataFrame.

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
    >>> df = run_wikidata_query(city_url)
    """
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
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
    
    SELECT ("{{CITY_URL}}" as ?sourceWikipediaURL) 
      ?sourceId ?targetId ?targetLabel
      ?starttime ?endtime
      ?retrieved ?referenceURL ?publisher ?title
    WHERE
    {
      {
        ?sourceId ^schema:about <{{CITY_URL}}> .
      }
      ?sourceId p:P190 ?statement.
      ?statement ps:P190 ?targetId.
    
      # rank - doesn't matter much - 3 possible values irrelevant for us
      #?statement wikibase:rank ?rank.
      # qualifiers
      OPTIONAL{ ?statement pq:P580 ?starttime. }
      OPTIONAL{ ?statement pq:P582 ?endtime. }
      # references
      OPTIONAL {
        ?statement prov:wasDerivedFrom ?refnode .
        ?refnode pr:P813 ?retrieved .
      }
      OPTIONAL {
        ?statement prov:wasDerivedFrom ?refnode .
        ?refnode pr:P854 ?referenceURL .
      }
      OPTIONAL {
        ?statement prov:wasDerivedFrom ?refnode .
        ?refnode pr:P123 ?publisher .
      }
      OPTIONAL {
        ?statement prov:wasDerivedFrom ?refnode .
        ?refnode pr:P1476 ?title .
      }
      SERVICE wikibase:label { 
        bd:serviceParam wikibase:language "en". 
        ?targetId rdfs:label ?targetLabel .
        # ?ref rdfs:label ?labelRef . # refs (retrieved, referenceURL, publisher, title) labels may be needed in the future
      }
    }
    """

    df = run_query(sparql, query, city_url)
    
    return df


# df = run_wikidata_query("https://en.wikipedia.org/wiki/Radom")
# print(df)
# df.to_csv("radom.csv", index=False)

# TODO: run_wikipedia_query (running sparql on rdflib Graph object?)
# TODO: diff representation (joining DataFrames)
