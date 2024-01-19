import os
import sys
import time
import urllib.parse
from dash import Dash, dcc, html, dash_table, callback_context
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_daq as daq

from grapher.twin_cities_graph import TwinCitiesGraph
from wikidata import queries as q
from wikidata.publish import Publisher

from layout_helper import run_standalone_app

EMPTY_VALUE = ""

DEBUG = False if os.getenv("PROD_MODE") else True


def header_colors():
    return {
        "bg_color": "#0C4142",
        "font_color": "white",
    }


def load_graph() -> TwinCitiesGraph:
    st = time.perf_counter()
    g = TwinCitiesGraph()
    g.load("./data/twin_cities.ttl")
    print(f"Loaded graph in {time.perf_counter() - st:0.2f} seconds")
    return g


graph: TwinCitiesGraph | None = None


def load_cities() -> list[dict[str, str]]:
    # List of city URLs for the dropdown
    st = time.perf_counter()
    cities = graph.get_cities()
    print(f"Got city URLs in {time.perf_counter() - st:0.2f} seconds")
    return [
        {"label": city["name"] + ", " + city["country"], "value": city["url"]}
        for city in cities
    ]


city_urls: list[dict[str, str]] = []


def load_twins_wikidata(city_url: str) -> list[dict[str, str | list[dict[str, str]]]]:
    st = time.perf_counter()
    raw = sorted(q.get_wikidata_twin_data(city_url), key=lambda x: x["targetLabel"])
    print(f"Ran query (wikidata) in {time.perf_counter() - st:0.2f} seconds")
    # remap keys
    data_wikidata = []
    for i in range(len(raw)):
        raw[i]["url"] = urllib.parse.unquote(raw[i].pop("targetUrl"))
        raw[i]["name"] = raw[i].pop("targetLabel")

        if (
            i > 0
            and raw[i]["targetId"] == raw[i - 1]["targetId"]
            and "referenceUrl" in raw[i]
        ):
            data_wikidata[-1]["references"].append(raw[i]["referenceUrl"])
        else:
            data_wikidata.append({**raw[i]})
            data_wikidata[-1]["references"] = []
            if "referenceUrl" in data_wikidata[-1]:
                data_wikidata[-1]["references"].append(
                    {
                        "url": data_wikidata[-1].pop("referenceUrl"),
                        "name": data_wikidata[-1].pop("referenceName")
                        if "referenceName" in data_wikidata[-1]
                        else None,
                        "publisher": data_wikidata[-1].pop("referencePublisher")
                        if "referencePublisher" in data_wikidata[-1]
                        else None,
                    }
                )
    return data_wikidata


def load_twins_wikipedia(city_url: str) -> list[dict[str, str]]:
    st = time.perf_counter()
    data_wikipedia = sorted(graph.get_twins(city_url), key=lambda x: x["name"])
    print(f"Ran query (wikipedia) in {time.perf_counter() - st:0.2f} seconds")
    return data_wikipedia


def align(
    data_1: list[dict[str, str]], data_2: list[dict[str, str]]
) -> list[dict[str, dict[str, str]]]:
    data = []
    i = 0
    j = 0
    while i < len(data_1) and j < len(data_2):
        if data_1[i]["url"] != data_2[j]["url"]:
            if data_1[i]["name"] == data_2[j]["name"]:
                data.append({"wikidata": data_1[i], "wikipedia": data_2[j]})
                i += 1
                j += 1
            else:
                if data_1[i]["url"] < data_2[j]["url"]:
                    data.append({"wikidata": data_1[i]})
                    i += 1
                elif data_1[i]["url"] > data_2[j]["url"]:
                    data.append({"wikipedia": data_2[j]})
                    j += 1
        else:
            data.append({"wikidata": data_1[i], "wikipedia": data_2[j]})
            i += 1
            j += 1
    while i < len(data_1):
        data.append(
            {
                "wikidata": data_1[i],
            }
        )
        i += 1
    while j < len(data_2):
        data.append({"wikipedia": data_2[j]})
        j += 1
    return data


def mask_url(url: str | None, prop: str) -> str | None:
    if prop != "url":
        return url
    if url is None:
        return None
    return f"<a href='{url}' target='_blank' >{url}</a>"


def mask_none(value: str | None) -> str:
    if value is None:
        return EMPTY_VALUE
    return value


twins_details: list[dict[str, dict[str, str]]] = []
twins_names: list[dict[str, str | int]] = []
references: list[dict[str, dict[str, str]]] = []
references_names = [
    "url",
    "name",
    "website",
    "publisher",
    "language",
    "accessDate",
    "date",
]


def setup():
    global graph, city_urls
    graph = load_graph()
    city_urls = load_cities()


STYLE_DATA_CONDITIONAL = [
    {
        "if": {
            "state": "selected",
        },
        "backgroundColor": "rgba(75, 75, 255, 0.2)",
        "border": "1px solid rgb(75, 75, 255)",
    },
]


def layout():
    return html.Div(
        id="app-body",
        className="app-body",
        children=[
            dcc.Store(id="memory"),
            html.Div(
                [
                    html.Div(
                        className="control-tab three columns",
                        children=[
                            html.H4(className="what-is", children="What is this app"),
                            html.P(
                                """
                    This application is going to help to complete
                    information in Wikidata about Twin Cities.
                    """
                            ),
                            html.P(
                                """
                    It will allow you to compare information from
                    Wikipedia and Wikidata and update Wikidata.
                    
                    Firstly select Tab Twin city comparison than provide city for which you want to compare information.
                    Click on Run Query button to get table of twin cities of selected city from Wikipedia and Wikidata.
                    You can select the twin city from the table and see the details of the city and references in the twin city edition tab.
                    If you want to update the Wikidata, select the references and click on Update Wikidata button.
                    """
                            ),
                            html.P(
                                """
                                This application is part of the project for the course Knowledge Graphs at Warsaw University of Technology.
                                """
                            ),
                        ],
                    ),
                    html.Div(
                        id="nine columns",
                        className="",
                        children=[
                            dcc.Tabs(
                                id="multiple-tabs",
                                value="what-is",
                                children=[
                                    dcc.Tab(
                                        label="Twin city comparision",
                                        value="twin-list",
                                        children=html.Div(
                                            className="single-tab",
                                            children=[
                                                html.Div(
                                                    className="search-div",
                                                    children=[
                                                        html.Div(
                                                            className="dropdown-div nine columns",
                                                            children=[
                                                                dcc.Dropdown(
                                                                    id="city-url",
                                                                    className="",
                                                                    options=[],
                                                                    placeholder="Select a city",
                                                                ),
                                                            ],
                                                        ),
                                                        html.Button(
                                                            "Run Query",
                                                            id="run-button",
                                                            className="three columns",
                                                        ),
                                                    ],
                                                ),
                                                daq.BooleanSwitch(
                                                    label="Show only twin cities from Wikipedia",
                                                    id="hide-switch",
                                                    on=False,
                                                    labelPosition="top",
                                                    style={
                                                        "margin-top": "10px",
                                                        "margin-bottom": "10px",
                                                    },
                                                ),
                                                html.Div(
                                                    id="output-table",
                                                    className="table twin-cities-table",
                                                    children=[
                                                        dash_table.DataTable(
                                                            id="dash-table",
                                                            columns=[
                                                                {
                                                                    "name": i,
                                                                    "id": i.lower(),
                                                                }
                                                                for i in [
                                                                    "Wikipedia",
                                                                    "Wikidata",
                                                                ]
                                                            ],
                                                            row_selectable="single",
                                                            fixed_rows={
                                                                "headers": True
                                                            },
                                                            style_cell={
                                                                "textAlign": "left",
                                                                "width": "50%",
                                                                "max-height": "300px",
                                                                "overflow": "auto",
                                                            },
                                                            style_data_conditional=[
                                                                {
                                                                    "if": {
                                                                        "filter_query": "{wikipedia} is nil",
                                                                        "column_id": "wikipedia",
                                                                    },
                                                                    "backgroundColor": "rgb(255, 175, 175, 0.5)",
                                                                },
                                                                {
                                                                    "if": {
                                                                        "filter_query": "{wikidata} is nil",
                                                                        "column_id": "wikidata",
                                                                    },
                                                                    "backgroundColor": "rgb(175, 255, 175, 0.5)",
                                                                },
                                                                {
                                                                    "if": {
                                                                        "filter_query": "!({wikipedia} is nil) && {wikidata} is nil",
                                                                        "column_id": "wikipedia",
                                                                    },
                                                                    "backgroundColor": "rgba(255, 175, 175, 0.5)",
                                                                },
                                                                {
                                                                    "if": {
                                                                        "state": "selected",
                                                                    },
                                                                    "backgroundColor": "rgba(75, 75, 255, 0.2)",
                                                                    "border": "1px solid rgb(75, 75, 255)",
                                                                },
                                                            ],
                                                        ),
                                                    ],
                                                    style={
                                                        "margin-top": "10px",
                                                        "margin-bottom": "10px",
                                                    },
                                                ),
                                                # style={'height': '100%', 'width': '40%', 'display': 'inline-block', 'vertical-align': 'top'}
                                            ],
                                        ),
                                    ),
                                    dcc.Tab(
                                        label="Twin City edition",
                                        value="twin-update",
                                        children=html.Div(
                                            className="single-tab",
                                            children=[
                                                html.Div(id="dash-div-details"),
                                                html.Div(
                                                    id="button-group",
                                                    children=[
                                                        html.Button(
                                                            "Select all properties",
                                                            id="select-all-button",
                                                            className="three columns",
                                                        ),
                                                        html.Button(
                                                            "Deselect all properties",
                                                            id="deselect-all-button",
                                                            className="three columns",
                                                        ),
                                                    ],
                                                ),
                                                dash_table.DataTable(
                                                    id="dash-table-refs",
                                                    row_selectable="multi",
                                                    markdown_options={"html": True},
                                                    columns=[
                                                        {
                                                            "name": "Property",
                                                            "id": "property",
                                                        },
                                                        {
                                                            "name": "Wikipedia",
                                                            "id": "wikipedia",
                                                            "presentation": "markdown",
                                                            "type": "text",
                                                        },
                                                        {
                                                            "name": "Wikidata",
                                                            "id": "wikidata",
                                                            "presentation": "markdown",
                                                            "type": "text",
                                                        },
                                                    ],
                                                    style_cell={
                                                        "textAlign": "left"
                                                    },  # , 'width': '33%'
                                                    style_data={
                                                        "whiteSpace": "normal"
                                                    },  # , 'height': 'auto'
                                                    style_table={
                                                        "margin-top": "10px"
                                                    },  # , 'width': '100%'
                                                    style_data_conditional=STYLE_DATA_CONDITIONAL,
                                                    css=[
                                                        {
                                                            "selector": "table",
                                                            "rule": "table-layout: fixed",
                                                        },
                                                        {
                                                            "selector": ".dash-cell div.dash-cell-value",
                                                            "rule": "overflow-wrap: break-word",
                                                        },
                                                        {
                                                            "selector": "p",
                                                            "rule": "margin: 0",
                                                        },
                                                        {
                                                            "selector": "div.dash-cell-value.cell-markdown",
                                                            "rule": "font-family: monospace",
                                                        },
                                                    ],
                                                ),
                                                html.Button(
                                                    "Update Wikidata",
                                                    id="update-button",
                                                    hidden=True,
                                                    style={
                                                        "margin-top": "10px",
                                                        "margin-bottom": "10px",
                                                        "width": "100%",
                                                    },
                                                ),
                                                dbc.Alert(
                                                    "ERROR !!! Something went wrong.",
                                                    id="error_alert",
                                                    is_open=False,
                                                    fade=True,
                                                    dismissable=True,
                                                    style={
                                                        "margin-top": "10px",
                                                        "margin-bottom": "10px",
                                                    },
                                                    color="danger",
                                                ),
                                                dbc.Alert(
                                                    "Update performed successfully !!!",
                                                    id="success_alert",
                                                    is_open=False,
                                                    fade=True,
                                                    dismissable=True,
                                                    style={
                                                        "margin-top": "10px",
                                                        "margin-bottom": "10px",
                                                    },
                                                    color="success",
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            )
                        ],
                    ),
                ]
            ),
        ],
    )


def callbacks(_app: Dash):
    @_app.callback(
        Output("update-button", "hidden", allow_duplicate=True),
        Output("memory", "data"),
        Input("update-button", "n_clicks"),
        State("city-url", "value"),
        State("dash-table", "selected_rows"),
        State("dash-table-refs", "selected_rows"),
        prevent_initial_call=True,
    )
    def query(n_clicks, city_url, selected_rows, selected_rows_refs):
        if (
            n_clicks is None
            or city_url is None
            or selected_rows is None
            or len(selected_rows) == 0
            or selected_rows_refs is None
            or len(selected_rows_refs) == 0
        ):
            return False, None

        source_id = None
        for details in twins_details:
            if "wikidata" in details:
                source_id = details["wikidata"]["sourceId"]
                break

        row = selected_rows[0]
        details = twins_details[row]

        refs = {}
        for i in selected_rows_refs:
            ref_i = i // len(references_names)
            if "wikipedia" in references[ref_i]:
                refs[ref_i] = {
                    **refs.get(ref_i, {}),
                    references_names[i % len(references_names)]: references[ref_i][
                        "wikipedia"
                    ][references_names[i % len(references_names)]],
                }

        update_object = {
            "sourceUrl": city_url,
            "sourceId": source_id,
            "twin": {
                **details.get("wikipedia", {}),
                "references": list(refs.values()),
            },
        }
        try:
            res = publisher.update(update_object)
            return True, res
        except Exception as e:
            message = str(e)
            return True, message

    @_app.callback(
        [Output("error_alert", "is_open"), Output("error_alert", "children")],
        Input("memory", "data"),
        prevent_initial_call=True,
    )
    def show_error_alert(data):
        if isinstance(data, str):
            return True, data
        return False, ""

    @_app.callback(
        Output("success_alert", "is_open"),
        Output("success_alert", "children"),
        Input("memory", "data"),
        prevent_initial_call=True,
    )
    def show_success_alert(data):
        if isinstance(data, bool) and data:
            return True, "Updated successfully"
        return False, ""

    @_app.callback(Output("city-url", "options"), Input("city-url", "search_value"))
    def update_options(search_value):
        if not search_value or len(search_value) < 3:
            # return [] # either clear previous search results or keep old ones
            raise PreventUpdate
        options = city_urls
        st = time.perf_counter()
        out = [o for o in options if search_value.lower() in o["label"].lower()][:100]
        print(f"Filtered options in {time.perf_counter() - st:0.2f} seconds")
        return out

    @_app.callback(
        Output("dash-div-details", "children", allow_duplicate=True),
        Output("dash-table-refs", "data", allow_duplicate=True),
        Output("dash-table-refs", "style_data_conditional"),
        Input("dash-table", "selected_rows"),
        State("city-url", "value"),
        prevent_initial_call=True,
    )
    def update_details_refs(selected_rows, city_url):
        if selected_rows is None or len(selected_rows) == 0:
            return None, None, STYLE_DATA_CONDITIONAL

        row = selected_rows[0]
        name = twins_names[row]
        details = twins_details[name["idx"]]

        target_wikipedia = details.get("wikipedia", {}).get("url", "")
        target_wikidata = details.get("wikidata", {}).get("targetId", "")

        source_wikidata = ""
        source_wikipedia = city_url or ""

        for details in twins_details:
            if "wikidata" in details:
                source_wikidata = details["wikidata"].get("sourceId", "")
                break

        div = html.Div(
            id="div-edit-details",
            children=[
                html.Div(
                    className="twelve columns",
                    children=[
                        html.Div(
                            className="div-edit-details-col",
                            children=[
                                html.P(
                                    [
                                        "Searched City: ",
                                        html.A(
                                            source_wikidata.removeprefix("http://"),
                                            href=source_wikidata,
                                            target="_blank",
                                        ),
                                    ]
                                ),
                                html.P(
                                    [
                                        "Searched City: ",
                                        html.A(
                                            source_wikipedia.removeprefix("https://"),
                                            href=source_wikipedia,
                                            target="_blank",
                                        ),
                                    ]
                                ),
                            ],
                        )
                    ],
                ),
                html.Div(
                    className="twelve columns",
                    children=[
                        html.Div(
                            className="div-edit-details-col",
                            children=[
                                html.P(
                                    [
                                        "Twin City: ",
                                        html.A(
                                            target_wikidata.removeprefix("http://"),
                                            href=target_wikidata,
                                            target="_blank",
                                        ),
                                    ]
                                ),
                                html.P(
                                    [
                                        "Twin City: ",
                                        html.A(
                                            target_wikipedia.removeprefix("https://"),
                                            href=target_wikipedia,
                                            target="_blank",
                                        ),
                                    ]
                                ),
                            ],
                        )
                    ],
                ),
            ],
        )

        references_wikipedia = []
        if "wikipedia" in details:
            references_wikipedia = graph.get_references(
                city_url, details["wikipedia"]["url"]
            )

        references_wikidata = []
        if "wikidata" in details:
            references_wikidata = details["wikidata"]["references"]

        global references
        references = align(references_wikidata, references_wikipedia)

        table = []
        for reference in references:
            for prop in references_names:
                table.append(
                    {
                        "property": prop,
                        "wikipedia": mask_none(
                            mask_url(reference.get("wikipedia", {}).get(prop), prop)
                        ),
                        "wikidata": mask_none(
                            mask_url(reference.get("wikidata", {}).get(prop), prop)
                        ),
                    }
                )
        _style_data_conditional = [
            *STYLE_DATA_CONDITIONAL,
            {
                "if": {
                    "row_index": [
                        i
                        for i in range(len(references) * len(references_names))
                        if (i // len(references_names)) % 2 == 0
                    ],
                },
                "backgroundColor": "rgb(220, 220, 220)",
            },
        ]
        return div, table, _style_data_conditional

    @_app.callback(
        Output("update-button", "hidden", allow_duplicate=True),
        Input("dash-table-refs", "selected_rows"),
        prevent_initial_call=True,
    )
    def update_button_hide(selected_rows):
        if selected_rows is None or len(selected_rows) == 0:
            return True
        return False

    @_app.callback(
        Output("dash-table", "data", allow_duplicate=True),
        Input("hide-switch", "on"),
        prevent_initial_call=True,
    )
    def update_table_hide(on):
        global twins_names
        twins_names = []
        for i, result in enumerate(twins_details):
            if on and "wikidata" in result:
                continue
            twins_names.append(
                {
                    "wikipedia": result.get("wikipedia", {}).get("name"),
                    "wikidata": result.get("wikidata", {}).get("name"),
                    "idx": i,
                }
            )
        return twins_names

    @_app.callback(
        Output("dash-table", "data"),
        Output("dash-div-details", "children"),
        Output("dash-table-refs", "data"),
        Output("hide-switch", "on"),
        Output("update-button", "hidden"),
        Input("run-button", "n_clicks"),
        State("city-url", "value"),
        prevent_initial_call=True,
    )
    def update_table(n_clicks, city_url):
        if n_clicks is None:
            return None, None, None, False, True  # Not clicked yet

        data_wikidata = load_twins_wikidata(city_url)
        data_wikipedia = load_twins_wikipedia(city_url)

        global twins_details, twins_names
        twins_details = align(data_wikidata, data_wikipedia)
        twins_names = []

        for i, result in enumerate(twins_details):
            twins_names.append(
                {
                    "wikipedia": result.get("wikipedia", {}).get("name"),
                    "wikidata": result.get("wikidata", {}).get("name"),
                    "idx": i,
                }
            )
        return twins_names, None, None, False, True

    @_app.callback(
        Output("dash-table-refs", "selected_rows"),
        Input("select-all-button", "n_clicks"),
        Input("deselect-all-button", "n_clicks"),
        State("dash-table-refs", "data"),
    )
    def selection(
        select_n_clicks,
        deselect_n_clicks,
        original_rows,  # , filtered_rows, selected_rows
    ):
        ctx = callback_context.triggered[0]
        ctx_caller = ctx["prop_id"]
        # if filtered_rows is not None:
        if ctx_caller == "deselect-all-button.n_clicks":
            if deselect_n_clicks is None:
                raise PreventUpdate
            return []
        if select_n_clicks is None:
            raise PreventUpdate
        return list(range(len(original_rows)))


app = run_standalone_app(layout, callbacks, "Twin Cities", header_colors, __file__)
app.title = "Twin Cities"
server = app.server
publisher = Publisher()

if __name__ == "__main__":
    setup()
    app.run_server(debug=DEBUG)
