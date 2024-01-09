import dash
import sys

import os
import sys

import time

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)


from dash import dcc, html
from dash.dependencies import Input, Output
from wikidata import queries as q
from dash.exceptions import PreventUpdate


app = dash.Dash(__name__)

st = time.perf_counter()
graph = q.load_wikipedia_graph("../twin_cities.ttl")
print(f"Loaded graph in {time.perf_counter() - st:0.2f} seconds")

# List of city URLs for the dropdown
st = time.perf_counter()
city_urls_pd = q.get_available_cities_urls(graph)
print(f"Got city URLs in {time.perf_counter() - st:0.2f} seconds")

city_urls_pd["label"] = city_urls_pd["city_name"] + ', ' + city_urls_pd["city_country"]
city_urls_pd["value"] = city_urls_pd["city_url"]

city_urls = city_urls_pd[["label", "value"]].to_dict("records")


app.layout = html.Div([
    dcc.Dropdown(id='city-url', options=[], placeholder='Select a city'), # passing city_urls here will kill the app (loading 18k rows into the dropdown)
    html.Button('Run Query', id='run-button'),
    html.Div(id='output-table')
])


@app.callback(
    Output("city-url", "options"),
    Input("city-url", "search_value")
)
def update_options(search_value):
    if not search_value or len(search_value) < 3:
        # return [] # either clear previous search results or keep old ones
        raise PreventUpdate
    options = city_urls
    st = time.perf_counter()
    out = [o for o in options if search_value.lower() in o["label"].lower()][:100]
    print(f"Filtered options in {time.perf_counter() - st:0.2f} seconds")
    return out


@app.callback(
    Output('output-table', 'children'),
    [Input('run-button', 'n_clicks')],
    [dash.dependencies.State('city-url', 'value')]
)
def update_output(n_clicks, city_url):
    if n_clicks is None:
        return None  # Not clicked yet

    st = time.perf_counter()
    df = q.get_wikidata_twin_data(city_url)
    print(f"Ran query in {time.perf_counter() - st:0.2f} seconds")
    # print(df)

    # Create a nested list with hidden details
    # TODO: two columns and background (or some other way) to show 
    #       diff between wikipedia and wikidata results (css classes same/different-a/different-b like in git green/red)
    nested_list = html.Ul([
        html.Li([
            html.Details([
                html.Summary(df.iloc[i]['targetLabel']),
                html.Ul([
                    html.Li(f"{col}: {df.iloc[i][col]}") for col in df.columns
                ])
            ])
        ]) for i in range(min(len(df), 20))
    ])

    return nested_list

if __name__ == '__main__':
    app.run_server(debug=True)