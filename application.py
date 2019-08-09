import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    stocks = db.execute("SELECT symbol, SUM(quantity) AS quantities FROM transactions WHERE id = :id GROUP BY symbol HAVING quantities > 0", id=session["user_id"])

    symbols = []
    for stock in stocks:
        symbols.append(stock["symbol"])

    prices = []
    for stock in stocks:
        result = lookup(stock["symbol"])
        price = result["price"]
        prices.append(price)

    a = 0
    for stock in stocks:
        stock.update({"cur_price" : prices[a]})
        a = a + 1

    for stock in stocks:
        tot_val = stock["quantities"] * stock["cur_price"]
        stock.update({"total_value" : tot_val})

    port_val = 0
    for stock in stocks:
        port_val = stock["total_value"] + port_val

    for stock in stocks:
        new_price = usd(stock["cur_price"])
        stock["cur_price"] = new_price
        new_value = usd(stock["total_value"])
        stock["total_value"] = new_value

    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

    return render_template("index.html", your_stocks=stocks, your_cash=usd(cash[0]["cash"]), your_val=usd(port_val+cash[0]["cash"]), your_symbols=symbols)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        stock_info = lookup(request.form.get("symbol"))

        if not stock_info:
            return apology("invalid stock symbol", 400)

        name = stock_info["name"]
        price = stock_info["price"]
        symbol = stock_info["symbol"]
        old = db.execute("SELECT * FROM transactions")

        if request.form.get("shares") < "1":
            return apology("enter a positive number of shares", 400)

        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        if not cash:
            return apology("error retrieving user data, try again", 400)

        if float(cash[0]["cash"]) < (int(request.form.get("shares")) * price):
            return apology("you do not have enough money for purchase", 400)
        else:
            db.execute("UPDATE users SET cash = (:original - :cost) where id = :id", original=float(cash[0]["cash"]), cost=int(request.form.get("shares"))*price, id=session["user_id"])

        db.execute("INSERT INTO transactions (id, stock, symbol, price_per, quantity, total, date) VALUES (:id, :stock, :symbol, :price_per, :quantity, :total, datetime('now'))", id=session["user_id"], stock=stock_info["name"], symbol=stock_info["symbol"], price_per=stock_info["price"], quantity=int(request.form.get("shares")), total=stock_info["price"]*int(request.form.get("shares")))
        new = db.execute("SELECT * FROM transactions")

        if len(old) >= len(new):
            return apology("Error updating transactions data", 400)
        else:
            return redirect("/")

    if request.method == "GET":
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    trans = db.execute("SELECT * FROM transactions WHERE id = :id", id=session["user_id"])

    for row in trans:
        tot = usd(row["total"] * -1)
        row.update({"total" : tot})
        dol = usd(row["price_per"])
        row.update({"price_per" : dol})
        if row["quantity"] < 0:
            row.update({"direction" : "Sold"})
        else:
            row.update({"direction" : "Bought"})

    return render_template("history.html", your_trans=trans)
    #return render_template("test.html", your_trans=trans)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached quote via POST
    if request.method == "POST":

        # Pass user input to lookup function and store in 'stock_price'
        stock_info = lookup(request.form.get("symbol"))

        if not stock_info:
            return apology("invalid stock symbol", 400)

        # Return stock_price to quoted.html to display info to user
        return render_template("quoted.html", st_name=stock_info["name"], st_price=usd(stock_info["price"]), st_symbol=stock_info["symbol"])

    # User reached quote via GET
    elif request.method == "GET":
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached register via POST
    if request.method == "POST":

        # Make sure user provides username
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Query database for username to make sure username not already in use
        test = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(test) > 0:
            return apology("username already in use, choose new username", 400)

        # Make sure user provides password
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Make sure user confirms password
        if not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Make sure password and confirmation are identical
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("confirmation does not match password", 400)

        # Hash user's password
        hash = generate_password_hash(request.form.get("password"))

        # Add user to users database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=hash)

        # Log user in after registration successful
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"] = rows[0]["id"]

        # Send user to homepage
        return redirect("/")

    # User reached register via GET
    if request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        stock_info = lookup(request.form.get("symbol"))
        if not stock_info:
            return apology("You do not own this stock", 400)

        if request.form.get("shares") < "1":
            return apology("Choose a positive number to sell", 400)

        your_shares = db.execute("SELECT SUM(quantity) AS quantity FROM transactions WHERE id = :id AND symbol = :symbol GROUP BY id", id=session["user_id"], symbol=request.form.get("symbol"))
        if int(your_shares[0]["quantity"]) < int(request.form.get("shares")):
            return apology("You do not own that many shares to sell", 400)

        quant_sold = int(request.form.get("shares"))
        curr_price = float(stock_info["price"])
        tot_val = quant_sold * curr_price
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        db.execute("UPDATE users SET cash = (:original + :sale) WHERE id = :id", original=cash[0]["cash"], sale=tot_val, id=session["user_id"])

        db.execute("INSERT INTO transactions (id, stock, price_per, quantity, total, symbol, date) VALUES (:id, :stock, :price_per, :quantity, :total, :symbol, datetime('now'))", id=session["user_id"], stock=stock_info["name"], price_per=curr_price, quantity=quant_sold*-1, total=tot_val*-1, symbol=request.form.get("symbol"))

        return redirect("/")
        #ADD SOME FAILSAFES HERE TO MAKE SURE TABLES UPDATED PROPERLY
        #return render_template("test.html", shares_of_your=request.form.get("shares"))

    if request.method == "GET":
        temp = db.execute("SELECT symbol FROM transactions WHERE id = :id GROUP BY symbol HAVING SUM(quantity) > 0", id=session["user_id"])
        symbols = []
        for stock in temp:
            symbols.append(stock["symbol"])

        return render_template("sell.html", your_symbols=symbols)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
