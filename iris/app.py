from iris.router import iris_classifier_router, dash_graph
from database.db_models import Stocks
from .database_sessions import SessionLocal
import database.database_helper as dbh
# fetch_stock_data_form_yfinance, add_bands, get_time_and_symbols
# from database.database_helper import get_stock_data_from_db
from .patterns import patterns
from .dashfigs import *

import dash
import plotly.graph_objs as obj
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
from starlette.middleware.wsgi import WSGIMiddleware

import sys
from enum import Enum

from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, Depends, BackgroundTasks
from pydantic import BaseModel

from sqlalchemy.orm import Session
import json

templates = Jinja2Templates(directory="template")
app = FastAPI()
app.include_router(iris_classifier_router.router, prefix='/iris')


class StocksRequest(BaseModel):
    symbol: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/dashboard")
async def dashboard(request: Request, forward_pe=None, dividend_yield=None, ma50=None, ma200=None,
                    db: Session = Depends(get_db)):
    print("\n\n\n\n\n\n\n\n shit \n\n\n\n\n\n\n\n")
    stocks_fetched = db.query(Stocks)
    # stocks_fetched = db.query(Stocks).all()

    # if (forward_pe is not None) and forward_pe != '' :
    if forward_pe:
        stocks_fetched = stocks_fetched.filter(Stocks.forward_pe < forward_pe)
        print(forward_pe)
    if dividend_yield:
        stocks_fetched = stocks_fetched.filter(Stocks.dividend_yield > dividend_yield)
    if ma50:
        stocks_fetched = stocks_fetched.filter(Stocks.price > Stocks.ma50)
    if ma200:
        stocks_fetched = stocks_fetched.filter(Stocks.price > Stocks.ma200)
    print(stocks_fetched)
    return templates.TemplateResponse("dashboard.html",
                                      {"request": request,
                                       "stocks": stocks_fetched,
                                       "divident_yield": dividend_yield,
                                       "forward_pe": forward_pe,
                                       "ma50": ma50,
                                       "ma200": ma200
                                       })


@app.get("/books")
async def get_books(books="books"):
    with open("./database/books.json") as file:
        books = json.load(file)
    return {books}


@app.get("/books/{title}")
async def get_books(title):
    with open("./database/books.json") as file:
        books = json.load(file)
    book = [b for b in books if b["title"] == title]
    return {"books": book}


@app.post("/stock")
async def create_stock(stock_request: StocksRequest, background_tasks: BackgroundTasks,
                       db: Session = Depends(get_db)):
    """
    add one or more tickers to the database
    background task to use yfinance and load key statistics
    """

    stock = Stocks()
    # print("stock request is", stock_request)
    stock.symbol = stock_request.symbol
    db.add(stock)
    db.commit()

    background_tasks.add_task(dbh.fetch_stock_data_form_yfinance, stock.id)

    return {
        "code": "success",
        "message": f"stock {stock.symbol} was added to the database"
    }


# order matters
@app.get("/users/me")
async def read_user_me():
    return {"user_id": "the current user"}


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    return {"user_id": user_id}


@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


@app.get("/model/{model_name}")
async def get_model(model_name: ModelName):
    if model_name == ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}
    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}
    return {"model_name": model_name, "message": "Have some residuals"}


@app.get('/healthcheck', status_code=200)
async def healthcheck():
    return 'Iris classifier is all ready to go!'


# @app.get("/")
# def home(request: Request, forward_pe=None, dividend_yield=None, ma50=None, ma200=None, db: Session = Depends(get_db)):
#     """
#     show all stocks in the database and button to add more
#     button next to each stock to delete from database
#     filters to filter this list of stocks
#     button next to each to add a note or save for later
#     """
#
#     stocks = db.query(Stocks)
#
#     if forward_pe:
#         stocks = stocks.filter(Stocks.forward_pe < forward_pe)
#
#     if dividend_yield:
#         stocks = stocks.filter(Stocks.dividend_yield > dividend_yield)
#
#     if ma50:
#         stocks = stocks.filter(Stocks.price > Stocks.ma50)
#
#     if ma200:
#         stocks = stocks.filter(Stocks.price > Stocks.ma200)
#
#     stocks = stocks.all()
#
#     return templates.TemplateResponse("home.html", {
#         "request": request,
#         "stocks": stocks,
#         "dividend_yield": dividend_yield,
#         "forward_pe": forward_pe,
#         "ma200": ma200,
#         "ma50": ma50
#     })


dashapp = dash.Dash(__name__, requests_pathname_prefix="/dash/")


def get_fig_test(dashapp):
    pass


dashapp.layout, slider = dash_graph.make_layout()


@dashapp.callback(Output("temp-plot", "figure"),
                  [Input("slider", "value"),
                   Input("submit_symbol_b", "n_clicks"),
                   State("input_symbol", "value"),
                   ])
def add_graph(slider, n_clicks, input_symbol):
    last, today, symbols = get_time_and_symbols()
    if input_symbol not in symbols:
        print("Symbol is not in S&P500, Please input a correct symbol")
        trace_high = obj.Scatter(x=[1, 3, 5], y=[2, 3, 1], mode="markers", name="High Temperatures")
        figure = obj.Figure(data=[trace_high])
        return figure

    df_stock = get_stock_data_from_db(last, symbs=input_symbol)
    # df = df.droplevel(1)
    print(__name__, input_symbol, n_clicks, not df_stock is None)
    if not df_stock is None:
        df_stock, _ = dbh.add_bands(df_stock)
        df_stock.sort_index(inplace=True)
        df_stock = df_stock.droplevel('symbol')

        candlestic = go.Candlestick(x=df_stock.index, open=df_stock['open'],
                                    high=df_stock['high'], low=df_stock['low'], close=df_stock['close'])
        upper_band = go.Scatter(x=df_stock.index, y=df_stock['upperbollinger'], name="Upper Bollinger Band",
                                line={'color': 'red'})
        lower_band = go.Scatter(x=df_stock.index, y=df_stock['lowerbollinger'], name="Lower Bollinger Band",
                                line={'color': 'red'})
        upper_keltner = go.Scatter(x=df_stock.index, y=df_stock['upperkeltner'], name="Upper Keltner Band",
                                   line={'color': 'blue'})
        lower_keltner = go.Scatter(x=df_stock.index, y=df_stock['lowerkeltner'], name="Lower Keltner Band",
                                   line={'color': 'blue'})

        sma = go.Scatter(x=df_stock.index, y=df_stock['20sma'], name="Moving Average")
        tes = go.Scatter(x=df_stock.index, y=df_stock['close'], name='close')
        fig1 = go.Figure(data=[candlestic, upper_band, lower_band, upper_keltner, lower_keltner, sma])
        # fig1 = go.Figure(data=[candlestic, sma, tes])
        # fig1 = go.Figure(data=[candlestic])
        # # fig1.update_layout(  # autosize=False, margin=dict(l=50,r=50, b=100,  t=100, pad=4 ),
        # #     height=1000,  # height=1000,  paper_bgcolor="LightSteelBlue",
        # # )
        # # print("giving figure out")
        return fig1
    else:
        trace_high = obj.Scatter(x=[1, 3, 5], y=[2, 3, 1], mode="markers", name="High Temperatures")
        # trace_low = obj.Scatter(x=df["Year"], y=df["TempLow"], mode="markers", name="Low Temperatures")
        # layout = obj.Layout(xaxis=dict(range=[slider[0], slider[1]]), yaxis={"title": "Temperature"})
        figure = obj.Figure(data=[trace_high])
        return figure


app.mount("/dash", WSGIMiddleware(dashapp.server))


@app.get("/")
async def home(request: Request):
    last, today, symbols = get_time_and_symbols()
    is_potential = ["Ha", "na"]
    for symb in symbols[:20]:
        df = get_stock_data_from_db(last, symbs=symb)
        _,_is_potential = dbh.add_bands(df)
        if _is_potential:
            is_potential.append(symb)
            print(symb)

    df = get_stock_data_from_db(last, "MSFT")
    return templates.TemplateResponse("home.html", {"request": request,
                                                    "patterns": patterns,
                                                    "is_potential": is_potential,
                                                    "stockdata": df.tail()})
