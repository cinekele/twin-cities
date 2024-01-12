import os
import sys
import time
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from grapher.twin_cities_graph import TwinCitiesGraph
from wikidata import queries as q

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

app = dash.Dash(__name__)


def load_graph() -> TwinCitiesGraph:
    st = time.perf_counter()
    g = TwinCitiesGraph()
    g.load("../twin_cities.ttl")
    print(f"Loaded graph in {time.perf_counter() - st:0.2f} seconds")
    return g


graph = load_graph()


def load_cities() -> list[dict[str, str]]:
    # List of city URLs for the dropdown
    st = time.perf_counter()
    cities = graph.get_cities()
    print(f"Got city URLs in {time.perf_counter() - st:0.2f} seconds")
    return [{"label": city["name"] + ', ' + city["country"], "value": city["url"]} for city in cities]


city_urls = load_cities()


def load_twins_wikidata(city_url: str) -> list[dict[str, str]]:
    st = time.perf_counter()
    data_wikidata = sorted(q.get_wikidata_twin_data(city_url), key=lambda x: x['targetLabel'])
    print(f"Ran query (wikidata) in {time.perf_counter() - st:0.2f} seconds")
    # remap keys
    for i in range(len(data_wikidata)):
        data_wikidata[i]['url'] = data_wikidata[i].pop('targetId')
        data_wikidata[i]['name'] = data_wikidata[i].pop('targetLabel')
    return data_wikidata


def load_twins_wikipedia(city_url: str) -> list[dict[str, str]]:
    st = time.perf_counter()
    data_wikipedia = sorted(graph.get_twins(city_url), key=lambda x: x['name'])
    print(f"Ran query (wikipedia) in {time.perf_counter() - st:0.2f} seconds")
    return data_wikipedia


twins_details: list[dict[str, dict[str, str]]] = []
twins_names: list[dict[str, str]] = []
references: list[dict[str, str]] = []
details_names = ["name", "url"]

app.layout = html.Div([
    html.Div([
        dcc.Dropdown(id='city-url', options=[], placeholder='Select a city'),
        html.Button('Run Query', id='run-button', style={'margin-top': '10px', 'margin-bottom': '10px'}),
        html.Div(id='output-table'),
        dash_table.DataTable(id='dash-table',
                             fixed_rows={'headers': True},
                             style_cell={'textAlign': 'left'},
                             style_data_conditional=[
                                 {
                                     'if': {
                                         'filter_query': '{wikipedia} != {wikidata}'
                                     },
                                     'backgroundColor': 'lightpink',
                                 }
                             ]),
    ],
        style={'height': '100%', 'width': '40%', 'display': 'inline-block', 'vertical-align': 'top'}),
    html.Div([
        dash_table.DataTable(id='dash-table-details', style_cell={'textAlign': 'left'}, style_table={'margin-top': '10px'}),
        dash_table.DataTable(id='dash-table-refs', style_cell={'textAlign': 'left'}, style_table={'margin-top': '10px'}),
        ],
        style={'width': '40%', 'display': 'inline-block', 'margin-left': '5%'}
    )],
    style={'height': '100%', 'width': '100%'}
)


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
    Output('dash-table-refs', 'data', allow_duplicate=True),
    Input('dash-table-details', 'active_cell'),
    State('dash-table', 'active_cell'),
    prevent_initial_call=True,
)
def update_refs(active_cell, active_cell_main):
    if active_cell is None or active_cell_main is None:
        return None

    row_main = active_cell_main['row']
    row = active_cell['row']
    details = twins_details[row_main]['wikipedia']
    if details is not None and row >= len(details_names):
        reference = references[row - len(details_names)]
        table = []
        for key, value in reference.items():
            table.append({
                "property": key,
                "wikipedia": value,
                "wikidata": None
            })
        return table
    return None


@app.callback(
    Output('dash-table-details', 'data', allow_duplicate=True),
    Output('dash-table-refs', 'data', allow_duplicate=True),
    Input('dash-table', 'active_cell'),
    prevent_initial_call=True,
)
def update_details(active_cell):
    if active_cell is None:
        return None, None

    row = active_cell['row']
    details = twins_details[row]
    table = []
    for details_name in details_names:
        table.append({
            "property": details_name,
            "wikipedia": details['wikipedia'][details_name] if details['wikipedia'] is not None else None,
            "wikidata": details['wikidata'][details_name] if details['wikidata'] is not None else None
        })
    if details['wikipedia'] is not None:
        global references
        references = graph.get_references(details['wikipedia']['url'])
        for reference in references:
            table.append({
                "property": "reference",
                "wikipedia": reference['name'],
                "wikidata": None
            })
    return table, None


@app.callback(
    Output('dash-table', 'data'),
    Output('dash-table-details', 'data'),
    Output('dash-table-refs', 'data'),
    [Input('run-button', 'n_clicks')],
    [dash.dependencies.State('city-url', 'value')],
    prevent_initial_call=True,
)
def update_table(n_clicks, city_url):
    if n_clicks is None:
        return None, None, None  # Not clicked yet

    data_wikidata = load_twins_wikidata(city_url)
    data_wikipedia = load_twins_wikipedia(city_url)

    global twins_details, twins_names
    twins_details = []
    twins_names = []
    i = 0
    j = 0
    while i < len(data_wikidata) and j < len(data_wikipedia):
        if data_wikidata[i]['name'] < data_wikipedia[j]['name']:
            twins_details.append({
                "wikidata": data_wikidata[i],
                "wikipedia": None
            })
            i += 1
        elif data_wikidata[i]['name'] > data_wikipedia[j]['name']:
            twins_details.append({
                "wikidata": None,
                "wikipedia": data_wikipedia[j]
            })
            j += 1
        else:
            twins_details.append({
                "wikidata": data_wikidata[i],
                "wikipedia": data_wikipedia[j]
            })
            i += 1
            j += 1

    for result in twins_details:
        twins_names.append({"wikipedia": result['wikipedia']['name'] if result['wikipedia'] is not None else None,
                            "wikidata": result['wikidata']['name'] if result['wikidata'] is not None else None})
    return twins_names, None, None


if __name__ == '__main__':
    app.run_server(debug=True)
