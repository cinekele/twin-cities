import os
import sys
import time
import urllib.parse
from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_daq as daq

from grapher.twin_cities_graph import TwinCitiesGraph
from wikidata import queries as q

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

app = Dash(__name__)


def load_graph() -> TwinCitiesGraph:
    st = time.perf_counter()
    g = TwinCitiesGraph()
    g.load("../twin_cities.ttl")
    print(f"Loaded graph in {time.perf_counter() - st:0.2f} seconds")
    return g


graph: TwinCitiesGraph | None = None


def load_cities() -> list[dict[str, str]]:
    # List of city URLs for the dropdown
    st = time.perf_counter()
    cities = graph.get_cities()
    print(f"Got city URLs in {time.perf_counter() - st:0.2f} seconds")
    return [{"label": city["name"] + ', ' + city["country"], "value": city["url"]} for city in cities]


city_urls: list[dict[str, str]] = []


def load_twins_wikidata(city_url: str) -> list[dict[str, str | list[dict[str, str]]]]:
    st = time.perf_counter()
    raw = sorted(q.get_wikidata_twin_data(city_url), key=lambda x: x['targetLabel'])
    print(f"Ran query (wikidata) in {time.perf_counter() - st:0.2f} seconds")
    # remap keys
    data_wikidata = []
    for i in range(len(raw)):
        raw[i]['url'] = urllib.parse.unquote(raw[i].pop('targetUrl'))
        raw[i]['name'] = raw[i].pop('targetLabel')

        if i > 0 and raw[i]['targetId'] == raw[i - 1]['targetId'] and 'referenceUrl' in raw[i]:
            data_wikidata[-1]['references'].append(raw[i]['referenceUrl'])
        else:
            data_wikidata.append({**raw[i]})
            data_wikidata[-1]['references'] = []
            if 'referenceUrl' in data_wikidata[-1]:
                data_wikidata[-1]['references'].append({
                    "url": data_wikidata[-1].pop('referenceUrl'),
                    "name": data_wikidata[-1].pop('referenceName') if 'referenceName' in data_wikidata[-1] else None,
                    "publisher": data_wikidata[-1].pop('referencePublisher') if 'referencePublisher' in data_wikidata[-1] else None,
                })
    return data_wikidata


def load_twins_wikipedia(city_url: str) -> list[dict[str, str]]:
    st = time.perf_counter()
    data_wikipedia = sorted(graph.get_twins(city_url), key=lambda x: x['name'])
    print(f"Ran query (wikipedia) in {time.perf_counter() - st:0.2f} seconds")
    return data_wikipedia


def align_twins(data_wikidata: list[dict[str, str]], data_wikipedia: list[dict[str, str]]) -> list[
    dict[str, dict[str, str]]]:
    twins = []
    i = 0
    j = 0
    while i < len(data_wikidata) and j < len(data_wikipedia):
        if data_wikidata[i]['url'] != data_wikipedia[j]['url']:
            if data_wikidata[i]['name'] == data_wikipedia[j]['name']:
                twins.append({
                    "wikidata": data_wikidata[i],
                    "wikipedia": data_wikipedia[j]
                })
                i += 1
                j += 1
            else:
                if data_wikidata[i]['url'] < data_wikipedia[j]['url']:
                    twins.append({
                        "wikidata": data_wikidata[i],
                        "wikipedia": None
                    })
                    i += 1
                elif data_wikidata[i]['url'] > data_wikipedia[j]['url']:
                    twins.append({
                        "wikidata": None,
                        "wikipedia": data_wikipedia[j]
                    })
                    j += 1
        else:
            twins.append({
                "wikidata": data_wikidata[i],
                "wikipedia": data_wikipedia[j]
            })
            i += 1
            j += 1
    return twins


twins_details: list[dict[str, dict[str, str]]] = []
twins_names: list[dict[str, str]] = []
references_wikipedia: list[dict[str, str]] = []
details_names = ["name", "url"]


def setup():
    global graph, city_urls
    graph = load_graph()
    city_urls = load_cities()


table_right_config = dict(
    markdown_options={'html': True},
    columns=[{"name": "property", "id": "property"},
             {"name": "wikipedia", "id": "wikipedia", "presentation": "markdown", "type": "text"},
             {"name": "wikidata", "id": "wikidata", "presentation": "markdown", "type": "text"}],
    style_cell={'textAlign': 'left', 'width': '33%'},
    style_data={'whiteSpace': 'normal', 'height': 'auto'},
    style_table={'margin-top': '10px', 'width': '100%'},
    css=[{'selector': 'table', 'rule': 'table-layout: fixed'},
         {'selector': '.dash-cell div.dash-cell-value', 'rule': 'overflow-wrap: break-word'},
         {'selector': 'p', 'rule': 'margin: 0'},
         {'selector': 'div.dash-cell-value.cell-markdown', 'rule': 'font-family: monospace'}]
)
EMPTY_VALUE = ""

app.layout = html.Div([
    html.Div([
        dcc.Dropdown(id='city-url', options=[], placeholder='Select a city'),
        html.Button('Run Query', id='run-button', style={'margin-top': '10px', 'margin-bottom': '10px'}),
        daq.BooleanSwitch(id='hide-switch', on=False, style={'margin-top': '10px', 'margin-bottom': '10px'}),
        html.Div(id='output-table'),
        dash_table.DataTable(id='dash-table',
                             columns=[{"name": i, "id": i} for i in ["wikipedia", "wikidata"]],
                             fixed_rows={'headers': True},
                             style_cell={'textAlign': 'left', 'width': '50%'},
                             style_data_conditional=[
                                 {
                                     'if': {
                                         'filter_query': '{wikipedia} is nil || {wikidata} is nil',
                                     },
                                     'backgroundColor': 'rgb(255, 175, 175)',
                                 }
                             ]),
    ],
        style={'height': '100%', 'width': '40%', 'display': 'inline-block', 'vertical-align': 'top'}),
    html.Div([
        dash_table.DataTable(id='dash-table-details',
                             **table_right_config),
        dash_table.DataTable(id='dash-table-refs',
                             **table_right_config),
    ],
        style={'width': '50%', 'display': 'inline-block', 'margin-left': '5%'}
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
    details = twins_details[row_main]
    if row >= len(details_names):
        if row - len(details_names) < len(references_wikipedia):
            reference = references_wikipedia[row - len(details_names)]
            table = []
            for key, value in reference.items():
                if value is None:
                    continue
                table.append({
                    "property": key,
                    "wikipedia": value if key != "url" else f"<a href='{value}' target='_blank' >{value}</a>",
                    "wikidata": EMPTY_VALUE
                })
            return table
        else:
            reference = details['wikidata']['references'][row - len(details_names) - len(references_wikipedia)]
            table = []
            for key, value in reference.items():
                if value is None:
                    continue
                table.append({
                    "property": key,
                    "wikipedia": EMPTY_VALUE,
                    "wikidata": value if key != "url" else f"<a href='{value}' target='_blank' >{value}</a>"
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
        field_wikipedia = details['wikipedia'][details_name] if details['wikipedia'] is not None else None
        field_wikidata = details['wikidata'][details_name] if details['wikidata'] is not None else None
        if details_name == "url":
            field_wikipedia = f"<a href='{field_wikipedia}' target='_blank' >{field_wikipedia}</a>" if field_wikipedia is not None else EMPTY_VALUE
            field_wikidata = f"<a href='{field_wikidata}' target='_blank' >{field_wikidata}</a>" if field_wikidata is not None else EMPTY_VALUE
        table.append({
            "property": details_name,
            "wikipedia": field_wikipedia if field_wikipedia is not None else EMPTY_VALUE,
            "wikidata": field_wikidata if field_wikidata is not None else EMPTY_VALUE
        })
    global references_wikipedia
    if details['wikipedia'] is not None:
        references_wikipedia = graph.get_references(details['wikipedia']['url'])
        for reference in references_wikipedia:
            table.append({
                "property": "reference",
                "wikipedia": reference['name'],
                "wikidata": EMPTY_VALUE
            })
    else:
        references_wikipedia = []
    if details['wikidata'] is not None:
        for reference in details['wikidata']['references']:
            table.append({
                "property": "reference",
                "wikipedia": EMPTY_VALUE,
                "wikidata": reference['name'] if reference['name'] is not None else reference['url']
            })
    return table, None


@app.callback(
    Output('dash-table', 'data', allow_duplicate=True),
    Input('hide-switch', 'on'),
    prevent_initial_call=True,
)
def update_table_hide(on):
    global twins_names
    twins_names = []
    for result in twins_details:
        if on and result['wikidata'] is not None:
            continue
        twins_names.append({"wikipedia": result['wikipedia']['name'] if result['wikipedia'] is not None else None,
                            "wikidata": result['wikidata']['name'] if result['wikidata'] is not None else None})
    return twins_names


@app.callback(
    Output('dash-table', 'data'),
    Output('dash-table-details', 'data'),
    Output('dash-table-refs', 'data'),
    Output('hide-switch', 'on'),
    Input('run-button', 'n_clicks'),
    State('city-url', 'value'),
    prevent_initial_call=True,
)
def update_table(n_clicks, city_url):
    if n_clicks is None:
        return None, None, None, False  # Not clicked yet

    data_wikidata = load_twins_wikidata(city_url)
    data_wikipedia = load_twins_wikipedia(city_url)

    global twins_details, twins_names
    twins_details = align_twins(data_wikidata, data_wikipedia)
    twins_names = []

    for result in twins_details:
        twins_names.append({"wikipedia": result['wikipedia']['name'] if result['wikipedia'] is not None else None,
                            "wikidata": result['wikidata']['name'] if result['wikidata'] is not None else None})
    return twins_names, None, None, False


if __name__ == '__main__':
    setup()
    app.run_server(debug=True)
