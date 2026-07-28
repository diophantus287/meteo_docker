from flask import Flask, render_template
import os
import random

app = Flask(__name__, template_folder="templates", static_folder="static")

PLOTS_FOLDER = "static/plots"

@app.route("/")
def index():

    plots = sorted(
        f for f in os.listdir(PLOTS_FOLDER)
        if f.lower().endswith(".png")
    )

    return render_template(
        "index.html",
        plots=plots,
        cache_id=random.randint(10000, 99999)
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
