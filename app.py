import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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
app.jinja_env.globals.update(usd=usd, lookup=lookup, int=int)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

now = datetime.now()
dt = now.strftime("%Y-%m-%d %H:%M:%S")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT * FROM stock WHERE id = :id ORDER BY symbol ASC", id=session["user_id"])
    users = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
    total = 0
    if not stocks:
        return render_template("/index.html", cash=usd(users[0]["cash"]))
    for i in range(len(stocks)):
        stock = lookup(stocks[i]["symbol"])
        stocks[i]["company"] = stock["name"]
        stocks[i]["cprice"] = float(stock["price"])
        stocks[i]["total"] = float(stocks[i]["cprice"]) * float(stocks[i]["quantity"])
        stocks[i]["total"] = float(stocks[i]["total"])
        total += stocks[i]["total"]
        grand_total = total + users[0]["cash"]
    return render_template("/index.html", stocks=stocks, cash=usd(users[0]["cash"]), total=usd(total), grand_total=usd(grand_total), gtt="Grand Total", t="Total")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if not request.form.get("symbol"):
            flash("Must provide symbol")
            return render_template("/error.html")
        elif int(request.form.get("shares")) <= 0:
            flash("Please provide positif number")
            return render_template("/error.html")
        quote = lookup(request.form.get("symbol"))
        if quote == None:
            flash("Stock symbol not valid, please try again")
            return render_template("/error.html")

        price = quote['price'] * int(request.form.get("shares"))
        curr_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        if curr_cash[0]["cash"] < price:
            flash("Sorry insufficient funds")
            return render_template("/error.html")

        up_cash = db.execute("UPDATE users SET cash=cash-:price WHERE id=:id", price=price, id=session["user_id"])
        add_trans = db.execute("INSERT INTO trans (id, type, symbol, share, price, date) VALUES (:id, 'BUY', :symbol, :share, :price, :date)",
            id=session["user_id"], symbol=quote["symbol"], share=int(request.form.get("shares")), price=quote['price'], date=dt)

        curr_stock = db.execute("SELECT symbol FROM stock WHERE id=:id AND symbol=:symbol", symbol=quote["symbol"], id=session["user_id"])
        if not curr_stock:
            db.execute("INSERT INTO stock (id, symbol, quantity) VALUES (:id, :symbol, :quantity)",
                id=session["user_id"], symbol=quote["symbol"], quantity=int(request.form.get("shares")))

        else:
            db.execute("UPDATE stock SET quantity=quantity+:quantity WHERE id=:id AND symbol=:symbol",
                quantity=int(request.form.get("shares")), id=session["user_id"], symbol=quote["symbol"]);
        flash("Success Buy " + str(quote['name']) + " stock" + " Quantity: " + str(request.form.get("shares")))
        return redirect("/")

    else:
        return render_template("/buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    trans = db.execute("SELECT * FROM trans WHERE id=:id ORDER BY date DESC", id=session["user_id"])
    return render_template("/history.html", trans=trans)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("/error.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide Password")
            return render_template("/error.html")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid username and/or password")
            return render_template("/error.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Successfully signed in!")
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
    if request.method == "POST":
        if not request.form.get("symbol"):
            flash("Must provide stock symbol")
            return render_template("/error.html")

        quote = lookup(request.form.get("symbol"))

        if quote == None:
            flash("Stock symbol not valid, please try again")
            return render_template("/error.html")
        else:
            return render_template("quoted.html", quote=quote)

    else:
        return render_template("/quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("/error.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("/error.html")

        elif request.form.get("password") != request.form.get("confirmation"):
            flash("Password and Confirmation not same")
            return render_template("/error.html")

        username=request.form.get("username")
        hash_pass=generate_password_hash(request.form.get("password"))
        regs=db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_pass)
        flash("Registered")
        return redirect("/login")
    else:
        return render_template("/register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks = db.execute("SELECT * FROM stock WHERE id=:id", id=session["user_id"])
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        stock_q = db.execute("SELECT * FROM stock WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=quote["symbol"])
        if not request.form.get("shares"):
            flash("Quantity must be positive number")
            return render_template("/error.html")

        elif int(request.form.get ("shares")) > stock_q[0]['quantity']:
            flash("Not enough shares to do this transaction")
            return render_template("/error.html")

        cost = int(request.form.get("shares")) * quote['price']
        add_trans = db.execute("INSERT INTO trans (id, type, symbol, share, price, date) VALUES (:id, 'SELL', :symbol, :share, :price, :date)",
            id=session["user_id"], symbol=request.form.get("symbol"), share=(int(request.form.get("shares")) * -1), price=quote['price'], date=dt)

        if int(request.form.get("shares")) == stock_q[0]['quantity']:
            db.execute("DELETE FROM stock WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=quote["symbol"])
        else:
            db.execute("UPDATE stock SET quantity=quantity-:quantity WHERE id=:id AND symbol=:symbol",
                quantity=int(request.form.get("shares")), id=session["user_id"], symbol=quote["symbol"]);
        up_cash = db.execute("UPDATE users SET cash=cash+:cost WHERE id=:id", cost=cost, id=session["user_id"]);

        flash("Success Sell " + str(quote['name']) + " stock" + " Quantity: " + str(request.form.get("shares")))
        return redirect("/")
    else:
        return render_template("/sell.html", stocks=stocks)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
