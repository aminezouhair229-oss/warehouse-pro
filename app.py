from flask import Flask, request, render_template_string, jsonify, redirect, url_for
import sqlite3

app = Flask(__name__)
DB_NAME = "warehouse_pro.db"

# 1. Création dyal Base de Données
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                buy_price REAL DEFAULT 0.0,
                sell_price REAL DEFAULT 0.0
            )
        ''')
        conn.commit()

# 2. L'Interface Web + Mobile Scanner
HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Warehouse Pro - Stock & Prix</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://unpkg.com/html5-qrcode"></script>
    <style>
        body { background-color: #f4f6f9; }
        .card { border-radius: 12px; border: none; }
        .scan-result-box { border-left: 5px solid #0d6efd; background: #fff; }
        .price-badge { font-size: 1.1rem; padding: 8px 12px; }
    </style>
</head>
<body>
<div class="container py-4">
    <h2 class="text-center fw-bold mb-4">📦 Warehouse Pro: Stock & Prix</h2>

    <!-- Dashboard Résumé -->
    <div class="row g-3 mb-4 text-center">
        <div class="col-md-4">
            <div class="card p-3 shadow-sm bg-primary text-white">
                <h6>Total القطع فـ الستوك</h6>
                <h3 class="fw-bold mb-0">{{ total_items }}</h3>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card p-3 shadow-sm bg-dark text-white">
                <h6>راس المال فـ الستوك (Taman Chra)</h6>
                <h3 class="fw-bold mb-0">{{ "%.2f"|format(total_capital) }} DH</h3>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card p-3 shadow-sm bg-success text-white">
                <h6>الربح الصافي المتوقع</h6>
                <h3 class="fw-bold mb-0">+{{ "%.2f"|format(total_profit) }} DH</h3>
            </div>
        </div>
    </div>

    <div class="row g-4">
        <!-- Partie Scanner & Formulaire -->
        <div class="col-lg-5">
            <div class="card p-4 shadow-sm">
                <h5 class="fw-bold mb-3">📷 1. Scanni Code-Barres</h5>
                <div id="reader" style="width: 100%; margin: auto; border-radius: 8px; overflow: hidden;"></div>
                <div class="d-flex gap-2 justify-content-center my-2">
                    <button type="button" class="btn btn-outline-primary btn-sm" onclick="startScanner()">فتح الكاميرا</button>
                    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="stopScanner()">سد الكاميرا</button>
                </div>

                <!-- Carte Informations dyal Scan -->
                <div id="scan_info" class="p-3 my-3 rounded shadow-sm scan-result-box d-none">
                    <h5 id="info_title" class="fw-bold text-primary mb-2"></h5>
                    <div class="row text-center g-2 mt-2">
                        <div class="col-6">
                            <div class="p-2 bg-light rounded">
                                <small class="text-muted d-block">الستوك الحالي</small>
                                <strong id="info_stock" class="fs-5 text-dark">0</strong>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="p-2 bg-light rounded">
                                <small class="text-muted d-block">الربح فـ الحبة</small>
                                <strong id="info_profit" class="fs-5 text-success">0 DH</strong>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="p-2 bg-warning bg-opacity-10 border border-warning rounded">
                                <small class="text-muted d-block">بشحال شريتيه</small>
                                <strong id="info_buy" class="fs-5 text-dark">0 DH</strong>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="p-2 bg-success bg-opacity-10 border border-success rounded">
                                <small class="text-muted d-block">بشحال تبيعو</small>
                                <strong id="info_sell" class="fs-5 text-success">0 DH</strong>
                            </div>
                        </div>
                    </div>
                </div>

                <hr>
                <h5 class="fw-bold mb-3">📝 2. الدخلة والخرجة ديال السلعة</h5>
                <form method="POST" action="/update_stock">
                    <div class="mb-2">
                        <label class="form-label fw-semibold">Code-Barres</label>
                        <input type="text" id="barcode" name="barcode" class="form-control form-control-lg" placeholder="Scanni awla kteb code..." required autofocus oninput="checkProduct(this.value)">
                    </div>
                    <div class="mb-2">
                        <label class="form-label fw-semibold">سمية السلعة (Produit)</label>
                        <input type="text" id="name" name="name" class="form-control" placeholder="Matalan: Chargeur Samsung Original" required>
                    </div>
                    <div class="row g-2 mb-2">
                        <div class="col-6">
                            <label class="form-label fw-semibold text-danger">ثمن الشراء (DH)</label>
                            <input type="number" step="0.01" id="buy_price" name="buy_price" class="form-control" placeholder="0.00" required>
                        </div>
                        <div class="col-6">
                            <label class="form-label fw-semibold text-success">ثمن البيع (DH)</label>
                            <input type="number" step="0.01" id="sell_price" name="sell_price" class="form-control" placeholder="0.00" required>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">الكمية (Quantité)</label>
                        <input type="number" name="amount" class="form-control" value="1" min="1" required>
                    </div>

                    <div class="d-flex gap-2">
                        <button type="submit" name="action" value="add" class="btn btn-success w-50 py-2 fw-bold">➕ زيد فـ الستوك</button>
                        <button type="submit" name="action" value="remove" class="btn btn-danger w-50 py-2 fw-bold">➖ نقص من الستوك</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Partie Tableau dyal Sel3a -->
        <div class="col-lg-7">
            <div class="card p-4 shadow-sm">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 class="fw-bold mb-0">📊 قائمة السلعة والأثمنة</h5>
                    <input type="text" id="searchInput" class="form-control w-50" placeholder="🔍 قلب على سلعة أولا كود..." onkeyup="filterTable()">
                </div>
                <div class="table-responsive">
                    <table class="table table-hover align-middle" id="stockTable">
                        <thead class="table-dark">
                            <tr>
                                <th>Code</th>
                                <th>السلعة</th>
                                <th>الستوك</th>
                                <th>ثمن الشراء</th>
                                <th>ثمن البيع</th>
                                <th>الربح/حبة</th>
                                <th>مسح</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for p in products %}
                            <tr style="cursor: pointer;" onclick="selectRow('{{ p[1] }}')">
                                <td><code>{{ p[1] }}</code></td>
                                <td><strong>{{ p[2] }}</strong></td>
                                <td>
                                    <span class="badge {% if p[3] > 5 %}bg-success{% elif p[3] > 0 %}bg-warning text-dark{% else %}bg-danger{% endif %} fs-6">
                                        {{ p[3] }}
                                    </span>
                                </td>
                                <td>{{ "%.2f"|format(p[4]) }} DH</td>
                                <td class="fw-bold text-success">{{ "%.2f"|format(p[5]) }} DH</td>
                                <td class="text-primary fw-semibold">+{{ "%.2f"|format(p[5] - p[4]) }} DH</td>
                                <td>
                                    <a href="/delete/{{ p[0] }}" class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation(); return confirm('Bghiti t-msa7 had sel3a?');">🗑️</a>
                                </td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="7" class="text-center text-muted py-4">مازال ما دخلتي حتى سلعة للديبو.</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    let html5QrCode;

    function startScanner() {
        html5QrCode = new Html5Qrcode("reader");
        html5QrCode.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 250, height: 150 } },
            (decodedText) => {
                document.getElementById("barcode").value = decodedText;
                checkProduct(decodedText);
                stopScanner();
            }
        ).catch(err => alert("Khass t-fta7 l'caméra: " + err));
    }

    function stopScanner() {
        if (html5QrCode) {
            html5QrCode.stop().then(() => html5QrCode.clear());
        }
    }

    function selectRow(barcode) {
        document.getElementById("barcode").value = barcode;
        checkProduct(barcode);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function checkProduct(barcode) {
        const infoBox = document.getElementById("scan_info");
        if (!barcode.trim()) {
            infoBox.classList.add("d-none");
            return;
        }
        fetch('/api/product/' + encodeURIComponent(barcode.trim()))
            .then(res => res.json())
            .then(data => {
                infoBox.classList.remove("d-none");
                if (data.found) {
                    document.getElementById("name").value = data.name;
                    document.getElementById("buy_price").value = data.buy_price;
                    document.getElementById("sell_price").value = data.sell_price;

                    const profit = (data.sell_price - data.buy_price).toFixed(2);
                    document.getElementById("info_title").innerHTML = "✅ " + data.name;
                    document.getElementById("info_stock").innerText = data.quantity + " حبات";
                    document.getElementById("info_buy").innerText = data.buy_price.toFixed(2) + " DH";
                    document.getElementById("info_sell").innerText = data.sell_price.toFixed(2) + " DH";
                    document.getElementById("info_profit").innerText = "+" + profit + " DH";
                } else {
                    document.getElementById("info_title").innerHTML = "🆕 سلعة جديدة (مازال ما مسجلاش)";
                    document.getElementById("info_stock").innerText = "0";
                    document.getElementById("info_buy").innerText = "-- DH";
                    document.getElementById("info_sell").innerText = "-- DH";
                    document.getElementById("info_profit").innerText = "-- DH";
                }
            });
    }

    function filterTable() {
        let input = document.getElementById("searchInput").value.toLowerCase();
        let rows = document.querySelectorAll("#stockTable tbody tr");
        rows.forEach(row => {
            let text = row.innerText.toLowerCase();
            row.style.display = text.includes(input) ? "" : "none";
        });
    }
</script>
</body>
</html>
"""

# 3. Routes dyal Serveur
@app.route("/")
def index():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, barcode, name, quantity, buy_price, sell_price FROM products ORDER BY id DESC")
        products = c.fetchall()

    total_items = sum(p[3] for p in products)
    total_capital = sum(p[3] * p[4] for p in products)
    total_profit = sum(p[3] * (p[5] - p[4]) for p in products)

    return render_template_string(
        HTML_PAGE,
        products=products,
        total_items=total_items,
        total_capital=total_capital,
        total_profit=total_profit
    )

@app.route("/api/product/<barcode>")
def get_product(barcode):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, quantity, buy_price, sell_price FROM products WHERE barcode = ?", (barcode,))
        row = c.fetchone()
        if row:
            return jsonify({
                "found": True,
                "name": row[0],
                "quantity": row[1],
                "buy_price": row[2],
                "sell_price": row[3]
            })
        return jsonify({"found": False})

@app.route("/update_stock", methods=["POST"])
def update_stock():
    barcode = request.form.get("barcode").strip()
    name = request.form.get("name").strip()
    amount = int(request.form.get("amount", 1))
    buy_price = float(request.form.get("buy_price", 0))
    sell_price = float(request.form.get("sell_price", 0))
    action = request.form.get("action")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT quantity FROM products WHERE barcode = ?", (barcode,))
        row = c.fetchone()

        if row:
            new_qty = row[0] + amount if action == "add" else max(0, row[0] - amount)
            c.execute('''
                UPDATE products 
                SET quantity = ?, name = ?, buy_price = ?, sell_price = ? 
                WHERE barcode = ?
            ''', (new_qty, name, buy_price, sell_price, barcode))
        else:
            initial_qty = amount if action == "add" else 0
            c.execute('''
                INSERT INTO products (barcode, name, quantity, buy_price, sell_price) 
                VALUES (?, ?, ?, ?, ?)
            ''', (barcode, name, initial_qty, buy_price, sell_price))
        conn.commit()

    return redirect(url_for("index"))

@app.route("/delete/<int:product_id>")
def delete_product(product_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)