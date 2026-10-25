from flask import Flask, request, jsonify, Response
import sqlite3
import os
import csv
import io
import json
from datetime import datetime

app = Flask(__name__)
DB_NAME = os.path.join("/tmp", "mahaal_pro_v3.db") if os.name != "nt" else "mahaal_pro_v3.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # جدول السلعة والستوك
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'عام',
                quantity INTEGER DEFAULT 0,
                min_stock INTEGER DEFAULT 3,
                buy_price REAL DEFAULT 0.0,
                sell_price REAL DEFAULT 0.0
            )
        ''')
        # جدول المبيعات (Caisse POS)
        c.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                items_json TEXT NOT NULL,
                total_amount REAL NOT NULL,
                total_profit REAL NOT NULL,
                discount REAL DEFAULT 0.0,
                payment_method TEXT DEFAULT 'CASH',
                customer_name TEXT DEFAULT 'زبون عابر',
                created_at TEXT NOT NULL
            )
        ''')
        # جدول كناش الكريدي ( الزبناء )
        c.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                debt REAL DEFAULT 0.0
            )
        ''')
        # جدول المصاريف (Charges)
        c.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        # جدول سجل التحركات
        c.execute('''
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                product_name TEXT NOT NULL,
                move_type TEXT NOT NULL,
                qty INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()

init_db()

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Mahaal & Warehouse PRO MAX</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.6/dist/JsBarcode.all.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
        body { font-family: 'Cairo', sans-serif; background-color: #0b1120; color: #f8fafc; padding-bottom: 90px; }
        .glass { background: rgba(30, 41, 59, 0.88); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.08); }
        .nav-active { color: #38bdf8 !important; transform: translateY(-3px); }
        #reader video { border-radius: 14px; object-fit: cover; }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.2s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>

    <!-- Top Header -->
    <div class="glass sticky top-0 z-40 px-3 py-2.5 flex justify-between items-center shadow-lg">
        <div class="flex items-center gap-2">
            <div class="bg-gradient-to-tr from-sky-500 to-emerald-400 p-2 rounded-xl text-slate-950 font-black shadow">
                <i class="fa-solid fa-store text-lg"></i>
            </div>
            <div>
                <h1 class="font-black text-sm leading-none tracking-wide">MAHAAL <span class="text-sky-400">PRO MAX</span></h1>
                <span class="text-[10px] text-emerald-400 flex items-center gap-1 mt-0.5">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span> كيس + ستوك + كناش
                </span>
            </div>
        </div>
        <div class="flex gap-1.5">
            <button onclick="openAddModal()" class="bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold text-xs px-3 py-2 rounded-xl flex items-center gap-1 shadow">
                <i class="fa-solid fa-plus"></i> سلعة جديدة
            </button>
        </div>
    </div>

    <div class="max-w-lg mx-auto px-3 pt-3">

        <!-- ================= TAB 1: SCANNER & CAISSE POS ================= -->
        <div id="tab-scan" class="tab-content active">
            
            <!-- 4 Scan Modes -->
            <div class="glass rounded-2xl p-1.5 mb-3 grid grid-cols-4 gap-1 text-center text-[11px] font-bold">
                <button onclick="setScanMode('pos')" id="mode-pos" class="py-2 rounded-xl bg-sky-500 text-slate-950 font-extrabold transition">
                    <i class="fa-solid fa-cash-register block mb-0.5 text-sm"></i> بيع (Caisse)
                </button>
                <button onclick="setScanMode('info')" id="mode-info" class="py-2 rounded-xl text-slate-300 transition">
                    <i class="fa-solid fa-magnifying-glass block mb-0.5 text-sm text-sky-400"></i> كشف الثمن
                </button>
                <button onclick="setScanMode('out')" id="mode-out" class="py-2 rounded-xl text-slate-300 transition">
                    <i class="fa-solid fa-arrow-up-from-bracket block mb-0.5 text-sm text-rose-400"></i> إخراج (-1)
                </button>
                <button onclick="setScanMode('in')" id="mode-in" class="py-2 rounded-xl text-slate-300 transition">
                    <i class="fa-solid fa-arrow-right-to-bracket block mb-0.5 text-sm text-emerald-400"></i> إدخال (+1)
                </button>
            </div>

            <!-- Scanner Box -->
            <div class="glass rounded-2xl p-3.5 mb-3 text-center">
                <div id="scanner-placeholder" class="py-4">
                    <div class="flex justify-center gap-2">
                        <button onclick="startCamera()" class="bg-gradient-to-r from-sky-500 to-sky-400 text-slate-950 font-black px-5 py-2.5 rounded-xl shadow-lg flex items-center gap-2 text-xs">
                            <i class="fa-solid fa-barcode text-base"></i> فتح كاميرا السكانير
                        </button>
                        <label class="bg-slate-800 border border-slate-700 text-slate-200 font-bold px-4 py-2.5 rounded-xl cursor-pointer flex items-center gap-1.5 text-xs">
                            <i class="fa-solid fa-camera text-amber-400"></i> تصوير كود
                            <input type="file" accept="image/*" capture="environment" class="hidden" onchange="scanFromFile(this)">
                        </label>
                    </div>
                </div>

                <div id="reader" class="w-full hidden"></div>

                <div id="camera-controls" class="hidden mt-2.5 flex justify-center gap-2">
                    <button onclick="toggleTorch()" class="bg-amber-500/20 border border-amber-500/40 text-amber-300 px-3 py-1.5 rounded-xl text-xs font-bold">
                        <i class="fa-solid fa-bolt"></i> البيل (Flash)
                    </button>
                    <button onclick="stopCamera()" class="bg-rose-500/20 border border-rose-500/40 text-rose-300 px-3 py-1.5 rounded-xl text-xs font-bold">
                        <i class="fa-solid fa-stop"></i> سد الكاميرا
                    </button>
                </div>

                <!-- Manual Search / Barcode Input -->
                <div class="mt-3 pt-2.5 border-t border-slate-800/80 flex gap-1.5">
                    <input type="text" id="manual-barcode" placeholder="كتب الكود-بار أولا سمية السلعة..." 
                        class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500"
                        onkeypress="if(event.key === 'Enter') handleBarcode(this.value)">
                    <button onclick="handleBarcode(document.getElementById('manual-barcode').value)" class="bg-sky-500/20 border border-sky-500/40 px-3.5 rounded-xl text-sky-400">
                        <i class="fa-solid fa-check"></i>
                    </button>
                </div>
            </div>

            <!-- POS CART (سلة المبيعات - كيس المحل) -->
            <div id="pos-box" class="glass rounded-2xl p-4 mb-3 border-t-4 border-emerald-500">
                <div class="flex justify-between items-center mb-2.5">
                    <h3 class="font-black text-sm flex items-center gap-1.5 text-emerald-400">
                        <i class="fa-solid fa-basket-shopping"></i> سلة البيع (La Caisse)
                    </h3>
                    <button onclick="clearCart()" class="text-[11px] text-rose-400 hover:underline">إفراغ السلة</button>
                </div>

                <div id="cart-items" class="space-y-2 max-h-52 overflow-y-auto mb-3 text-xs">
                    <p class="text-center text-slate-500 py-4">السلة خاوية. سكاني سلعة أولا اختارها من القائمة باش تبيعها!</p>
                </div>

                <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-800 space-y-2 text-xs">
                    <div class="flex justify-between items-center">
                        <span class="text-slate-400">تخفيض للزبون (Remise DH):</span>
                        <input type="number" id="cart-discount" value="0" min="0" oninput="renderCart()" class="w-24 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-center font-bold text-amber-400">
                    </div>
                    <div class="flex justify-between items-center text-base font-black pt-1 border-t border-slate-800">
                        <span>المجموع الواجب أداؤه:</span>
                        <span id="cart-total" class="text-emerald-400 text-lg">0.00 DH</span>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-2 mt-3">
                    <button onclick="checkout('CASH')" class="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black py-2.5 rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-emerald-500/10">
                        <i class="fa-solid fa-money-bill-wave"></i> خلاص كاش (Cash)
                    </button>
                    <button onclick="checkout('CREDIT')" class="bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-2.5 rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-amber-500/10">
                        <i class="fa-solid fa-book"></i> قيدها كريدي (كناش)
                    </button>
                </div>
            </div>

            <!-- Scanned Product Detailed Info Card -->
            <div id="scan-result" class="hidden glass rounded-2xl p-4 border-r-4 border-sky-500 mb-4">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <span id="res-cat" class="text-[10px] bg-sky-500/20 text-sky-300 px-2 py-0.5 rounded"></span>
                        <h2 id="res-name" class="text-base font-black text-white mt-0.5"></h2>
                        <code id="res-code" class="text-[11px] text-slate-400"></code>
                    </div>
                    <div class="flex gap-1">
                        <button onclick="printBarcodeSticker(currentProduct)" class="bg-slate-800 p-2 rounded-lg text-xs text-amber-400" title="طباعة الكود-بار">
                            <i class="fa-solid fa-print"></i>
                        </button>
                        <button onclick="editCurrentProduct()" class="bg-slate-800 p-2 rounded-lg text-xs text-sky-400">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-2 text-center mb-3">
                    <div class="bg-slate-900 p-2.5 rounded-xl border border-slate-800">
                        <span class="text-[11px] text-slate-400 block">ثمن الشراء</span>
                        <strong id="res-buy" class="text-sm font-bold text-amber-400">0 DH</strong>
                    </div>
                    <div class="bg-emerald-500/10 p-2.5 rounded-xl border border-emerald-500/30">
                        <span class="text-[11px] text-emerald-300 block">ثمن البيع</span>
                        <strong id="res-sell" class="text-base font-black text-emerald-400">0 DH</strong>
                    </div>
                    <div class="bg-slate-900 p-2.5 rounded-xl border border-slate-800">
                        <span class="text-[11px] text-slate-400 block">الربح فـ الحبة</span>
                        <strong id="res-profit" class="text-sm font-bold text-sky-400">+0 DH</strong>
                    </div>
                    <div class="bg-slate-900 p-2.5 rounded-xl border border-slate-800">
                        <span class="text-[11px] text-slate-400 block">الستوك الحالي</span>
                        <strong id="res-qty" class="text-base font-black text-white">0</strong>
                    </div>
                </div>

                <div class="flex items-center gap-1.5 text-xs">
                    <input type="number" id="quick-qty" value="1" min="1" class="w-16 bg-slate-900 border border-slate-700 rounded-xl py-2 text-center font-bold">
                    <button onclick="addToCart(currentProduct, parseInt(document.getElementById('quick-qty').value)||1)" class="flex-1 bg-sky-500 text-slate-950 font-black py-2 rounded-xl">
                        🛒 للسلة
                    </button>
                    <button onclick="quickAdjust('add')" class="flex-1 bg-emerald-500 text-slate-950 font-black py-2 rounded-xl">
                        + ستوك
                    </button>
                    <button onclick="quickAdjust('remove')" class="flex-1 bg-rose-500 text-white font-black py-2 rounded-xl">
                        - ستوك
                    </button>
                </div>
            </div>
        </div>

        <!-- ================= TAB 2: STOCK & PRODUCTS ================= -->
        <div id="tab-products" class="tab-content">
            <div class="glass rounded-2xl p-2.5 mb-3 flex gap-2">
                <input type="text" id="search-input" oninput="renderProducts()" placeholder="🔍 قلب بالسمية، الكود، أولا الصنف..." 
                    class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500">
            </div>
            <div id="products-list" class="space-y-2"></div>
        </div>

        <!-- ================= TAB 3: KONNACH CREDIT (كناش الكريدي) ================= -->
        <div id="tab-credit" class="tab-content">
            <div class="glass p-4 rounded-2xl mb-3 border-r-4 border-amber-500 flex justify-between items-center">
                <div>
                    <span class="text-xs text-slate-400">مجموع الكريدي عند الزبناء</span>
                    <h3 id="total-credit-stat" class="text-2xl font-black text-amber-400 mt-0.5">0.00 DH</h3>
                </div>
                <button onclick="openCustomerModal()" class="bg-amber-500 text-slate-950 font-black text-xs px-3.5 py-2.5 rounded-xl flex items-center gap-1">
                    <i class="fa-solid fa-user-plus"></i> زبون جديد
                </button>
            </div>

            <div id="customers-list" class="space-y-2.5 text-xs"></div>
        </div>

        <!-- ================= TAB 4: BILAN & CHARGES (الحسابات والمصاريف) ================= -->
        <div id="tab-dash" class="tab-content">
            <div class="grid grid-cols-2 gap-2.5 mb-3">
                <div class="glass p-3.5 rounded-2xl border-r-4 border-emerald-500">
                    <span class="text-[11px] text-slate-400">مبيعات اليوم (Chiffre)</span>
                    <h3 id="stat-sales-today" class="text-lg font-black text-white mt-0.5">0.00 DH</h3>
                </div>
                <div class="glass p-3.5 rounded-2xl border-r-4 border-sky-500">
                    <span class="text-[11px] text-slate-400">ربح المبيعات الحقيقي</span>
                    <h3 id="stat-real-profit" class="text-lg font-black text-sky-400 mt-0.5">+0.00 DH</h3>
                </div>
                <div class="glass p-3.5 rounded-2xl border-r-4 border-rose-500">
                    <span class="text-[11px] text-slate-400">مجموع المصاريف (Charges)</span>
                    <h3 id="stat-expenses" class="text-lg font-black text-rose-400 mt-0.5">-0.00 DH</h3>
                </div>
                <div class="glass p-3.5 rounded-2xl border-r-4 border-amber-500">
                    <span class="text-[11px] text-slate-400">الربح الصافي بعد المصاريف</span>
                    <h3 id="stat-net-cash" class="text-lg font-black text-emerald-400 mt-0.5">0.00 DH</h3>
                </div>
            </div>

            <!-- Stock Valuation Card -->
            <div class="glass p-3.5 rounded-2xl mb-3 flex justify-between items-center text-xs">
                <div>
                    <span class="text-slate-400 block">راس المال فـ الستوك (<b id="stat-items">0</b> بياسة):</span>
                    <strong id="stat-capital" class="text-base text-amber-400 font-black">0.00 DH</strong>
                </div>
                <div class="text-left">
                    <span class="text-slate-400 block">ربح الستوك المتوقع:</span>
                    <strong id="stat-profit" class="text-base text-emerald-400 font-black">+0.00 DH</strong>
                </div>
            </div>

            <!-- Add Expense Box -->
            <div class="glass rounded-2xl p-3.5 mb-3">
                <h4 class="font-bold text-xs mb-2 text-rose-400 flex items-center gap-1.5">
                    <i class="fa-solid fa-file-invoice-dollar"></i> تسجيل مصروف جديد (كراء، سلعة، ترانسبور...)
                </h4>
                <form onsubmit="addExpense(event)" class="flex gap-1.5 text-xs">
                    <input type="text" id="exp-title" required placeholder="شنو هاد المصروف؟" class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white">
                    <input type="number" step="0.01" id="exp-amount" required placeholder="DH" class="w-24 bg-slate-900 border border-slate-700 rounded-xl px-2 py-2 text-white">
                    <button type="submit" class="bg-rose-500 text-white font-bold px-3.5 rounded-xl">+</button>
                </form>
                <div id="expenses-list" class="mt-2.5 space-y-1.5 max-h-36 overflow-y-auto text-[11px]"></div>
            </div>

            <!-- Low Stock Alerts -->
            <div class="glass rounded-2xl p-3.5 mb-3">
                <h4 class="font-bold text-xs mb-2 flex items-center gap-1.5 text-amber-400">
                    <i class="fa-solid fa-triangle-exclamation"></i> سلعة قربات تسالي (Stock Faible)
                </h4>
                <div id="low-stock-list" class="space-y-1.5 text-xs"></div>
            </div>
        </div>

        <!-- ================= TAB 5: HISTORY & BACKUP ================= -->
        <div id="tab-history" class="tab-content">
            <!-- Backup & Excel Tools -->
            <div class="glass rounded-2xl p-4 mb-3">
                <h4 class="font-bold text-xs mb-2.5 text-sky-400 flex items-center gap-1.5">
                    <i class="fa-solid fa-cloud-arrow-down"></i> حماية البيانات وتحميل التقارير
                </h4>
                <div class="grid grid-cols-3 gap-2 text-center text-[11px] font-bold">
                    <a href="/export_csv" class="bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 py-2.5 rounded-xl block">
                        <i class="fa-solid fa-file-excel block text-base mb-1"></i> تحميل Excel
                    </a>
                    <a href="/api/backup" class="bg-sky-500/20 border border-sky-500/40 text-sky-300 py-2.5 rounded-xl block">
                        <i class="fa-solid fa-download block text-base mb-1"></i> حفظ نسخة (Backup)
                    </a>
                    <label class="bg-amber-500/20 border border-amber-500/40 text-amber-300 py-2.5 rounded-xl cursor-pointer block">
                        <i class="fa-solid fa-upload block text-base mb-1"></i> استرجاع نسخة
                        <input type="file" accept=".json" class="hidden" onchange="restoreBackup(this)">
                    </label>
                </div>
            </div>

            <!-- Sales History -->
            <div class="glass rounded-2xl p-3.5 mb-3">
                <h4 class="font-bold text-xs mb-2.5 flex items-center gap-1.5 text-emerald-400">
                    <i class="fa-solid fa-receipt"></i> آخر المبيعات والتوصيلات (Tickets)
                </h4>
                <div id="sales-list" class="space-y-2 text-xs max-h-60 overflow-y-auto"></div>
            </div>

            <!-- Stock Movements -->
            <div class="glass rounded-2xl p-3.5">
                <h4 class="font-bold text-xs mb-2.5 flex items-center gap-1.5 text-sky-400">
                    <i class="fa-solid fa-clock-rotate-left"></i> سجل تحركات الستوك
                </h4>
                <div id="history-list" class="space-y-1.5 text-xs max-h-60 overflow-y-auto"></div>
            </div>
        </div>

    </div>

    <!-- Modal Add / Edit Product -->
    <div id="product-modal" class="fixed inset-0 bg-black/80 z-50 hidden flex items-center justify-center p-4">
        <div class="glass w-full max-w-md rounded-2xl p-5 border border-slate-700">
            <div class="flex justify-between items-center mb-3">
                <h3 class="font-bold text-sm">إضافة / تعديل سلعة فـ الديبو</h3>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <form id="product-form" onsubmit="saveProduct(event)" class="space-y-2.5 text-xs">
                <div>
                    <label class="block text-slate-300 mb-1">الكود-بار (Code-Barres)</label>
                    <div class="flex gap-1.5">
                        <input type="text" id="form-barcode" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white">
                        <button type="button" onclick="generateBarcode()" class="bg-slate-800 border border-slate-700 px-3 rounded-xl text-sky-400 whitespace-nowrap">
                            <i class="fa-solid fa-wand-magic-sparkles"></i> توليد كود
                        </button>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-slate-300 mb-1">سمية السلعة</label>
                        <input type="text" id="form-name" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white">
                    </div>
                    <div>
                        <label class="block text-slate-300 mb-1">الصنف (Catégorie)</label>
                        <input type="text" id="form-cat" value="عام" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-amber-400 mb-1 font-bold">ثمن الشراء (DH)</label>
                        <input type="number" step="0.01" id="form-buy" required class="w-full bg-slate-900 border border-amber-500/40 rounded-xl px-3 py-2 text-white">
                    </div>
                    <div>
                        <label class="block text-emerald-400 mb-1 font-bold">ثمن البيع (DH)</label>
                        <input type="number" step="0.01" id="form-sell" required class="w-full bg-slate-900 border border-emerald-500/40 rounded-xl px-3 py-2 text-white">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-slate-300 mb-1">الكمية فـ الستوك</label>
                        <input type="number" id="form-qty" value="1" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white">
                    </div>
                    <div>
                        <label class="block text-slate-300 mb-1">تنبيه الستوك القليل</label>
                        <input type="number" id="form-min" value="3" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white">
                    </div>
                </div>
                <button type="submit" class="w-full bg-sky-500 text-slate-950 font-black py-2.5 rounded-xl mt-2">
                    💾 حفظ السلعة
                </button>
            </form>
        </div>
    </div>

    <!-- Bottom App Navigation (5 Tabs) -->
    <div class="glass fixed bottom-0 inset-x-0 z-40 border-t border-slate-800 px-2 py-2 flex justify-around items-center text-[11px] text-slate-400">
        <button onclick="switchTab('scan', this)" class="flex flex-col items-center gap-0.5 nav-active transition">
            <i class="fa-solid fa-cash-register text-base"></i>
            <span class="font-bold">الكيس & سكان</span>
        </button>
        <button onclick="switchTab('products', this)" class="flex flex-col items-center gap-0.5 transition">
            <i class="fa-solid fa-boxes-stacked text-base"></i>
            <span class="font-bold">الستوك (<span id="nav-count">0</span>)</span>
        </button>
        <button onclick="switchTab('credit', this)" class="flex flex-col items-center gap-0.5 transition">
            <i class="fa-solid fa-book-open text-base"></i>
            <span class="font-bold">الكناش</span>
        </button>
        <button onclick="switchTab('dash', this)" class="flex flex-col items-center gap-0.5 transition">
            <i class="fa-solid fa-chart-line text-base"></i>
            <span class="font-bold">الحسابات</span>
        </button>
        <button onclick="switchTab('history', this)" class="flex flex-col items-center gap-0.5 transition">
            <i class="fa-solid fa-Sliders text-base fa-clock-rotate-left"></i>
            <span class="font-bold">السجل & نسخ</span>
        </button>
    </div>

<script>
    let allProducts = [];
    let allCustomers = [];
    let cart = [];
    let currentProduct = null;
    let scanMode = 'pos';
    let html5QrCode = null;
    let torchOn = false;
    let lastScanTime = 0;

    function playBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(1450, ctx.currentTime);
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.11);
            if (navigator.vibrate) navigator.vibrate(90);
        } catch(e) {}
    }

    function switchTab(tab, btn) {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.getElementById('tab-' + tab).classList.add('active');
        document.querySelectorAll('.fixed.bottom-0 button').forEach(b => b.classList.remove('nav-active'));
        btn.classList.add('nav-active');
        loadData();
    }

    function setScanMode(mode) {
        scanMode = mode;
        ['pos', 'info', 'out', 'in'].forEach(m => {
            const btn = document.getElementById('mode-' + m);
            btn.className = (m === mode) 
                ? "py-2 rounded-xl bg-sky-500 text-slate-950 font-extrabold transition shadow"
                : "py-2 rounded-xl text-slate-300 transition";
        });
    }

    function startCamera() {
        document.getElementById('scanner-placeholder').classList.add('hidden');
        document.getElementById('reader').classList.remove('hidden');
        document.getElementById('camera-controls').classList.remove('hidden');

        html5QrCode = new Html5Qrcode("reader", {
            experimentalFeatures: { useBarCodeDetectorIfSupported: true }
        });

        html5QrCode.start(
            { facingMode: "environment" },
            { fps: 15, qrbox: { width: 250, height: 115 }, aspectRatio: 1.333 },
            (decodedText) => {
                const now = Date.now();
                if (now - lastScanTime < 1600) return;
                lastScanTime = now;
                playBeep();
                handleBarcode(decodedText);
            }
        ).catch(() => {
            Swal.fire('تنبيه الكاميرا', 'عطي الصلاحية للكاميرا أولا استعمل زر "تصوير كود".', 'warning');
            stopCamera();
        });
    }

    function stopCamera() {
        if (html5QrCode && html5QrCode.isScanning) {
            html5QrCode.stop().then(() => {
                html5QrCode.clear();
                document.getElementById('reader').classList.add('hidden');
                document.getElementById('camera-controls').classList.add('hidden');
                document.getElementById('scanner-placeholder').classList.remove('hidden');
            });
        } else {
            document.getElementById('reader').classList.add('hidden');
            document.getElementById('camera-controls').classList.add('hidden');
            document.getElementById('scanner-placeholder').classList.remove('hidden');
        }
    }

    function toggleTorch() {
        if (!html5QrCode) return;
        torchOn = !torchOn;
        html5QrCode.applyVideoConstraints({ advanced: [{ torch: torchOn }] }).catch(() => {});
    }

    function scanFromFile(input) {
        if (input.files.length === 0) return;
        const fileScanner = new Html5Qrcode("reader");
        fileScanner.scanFile(input.files[0], true)
            .then(txt => { playBeep(); handleBarcode(txt); })
            .catch(() => Swal.fire('ما بانش الكود', 'عاود صور الكود من قريب وبوضوح', 'error'));
    }

    function handleBarcode(query) {
        query = (query || '').trim();
        if (!query) return;
        document.getElementById('manual-barcode').value = '';

        let found = allProducts.find(p => p.barcode === query || p.name.toLowerCase() === query.toLowerCase());

        if (!found) {
            Swal.fire({
                title: 'سلعة جديدة!',
                text: `الكود (${query}) ما مسجلش. بغيتي تزيدو دابا؟`,
                icon: 'info',
                showCancelButton: true,
                confirmButtonText: 'نعم، سجلها',
                cancelButtonText: 'إلغاء'
            }).then(res => { if (res.isConfirmed) openAddModal(query); });
            return;
        }

        currentProduct = found;
        showProductCard(found);

        if (scanMode === 'pos') {
            addToCart(found, 1);
        } else if (scanMode === 'out') {
            updateStockAPI(found.barcode, 1, 'remove');
        } else if (scanMode === 'in') {
            updateStockAPI(found.barcode, 1, 'add');
        }
    }

    // ================ POS CART FUNCTIONS ================
    function addToCart(product, qty = 1) {
        if (!product) return;
        const existing = cart.find(item => item.barcode === product.barcode);
        if (existing) {
            existing.qty += qty;
        } else {
            cart.push({
                barcode: product.barcode,
                name: product.name,
                buy_price: product.buy_price,
                sell_price: product.sell_price,
                qty: qty
            });
        }
        renderCart();
        Swal.fire({ toast: true, position: 'top', timer: 1000, showConfirmButton: false, icon: 'success', title: `تزادت ${product.name} للسلة` });
    }

    function changeCartQty(index, delta) {
        cart[index].qty += delta;
        if (cart[index].qty <= 0) cart.splice(index, 1);
        renderCart();
    }

    function clearCart() {
        cart = [];
        document.getElementById('cart-discount').value = 0;
        renderCart();
    }

    function renderCart() {
        const box = document.getElementById('cart-items');
        const discount = parseFloat(document.getElementById('cart-discount').value) || 0;

        if (cart.length === 0) {
            box.innerHTML = `<p class="text-center text-slate-500 py-3">السلة خاوية. سكاني سلعة باش تبيعها!</p>`;
            document.getElementById('cart-total').innerText = '0.00 DH';
            return;
        }

        let subtotal = 0;
        box.innerHTML = cart.map((item, idx) => {
            const lineTotal = item.sell_price * item.qty;
            subtotal += lineTotal;
            return `
                <div class="bg-slate-900/90 p-2 rounded-xl flex justify-between items-center border border-slate-800">
                    <div>
                        <b class="text-white block">${item.name}</b>
                        <span class="text-[11px] text-emerald-400">${item.sell_price.toFixed(2)} DH × ${item.qty} = <b>${lineTotal.toFixed(2)} DH</b></span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <button onclick="changeCartQty(${idx}, -1)" class="w-6 h-6 bg-slate-800 rounded-lg text-rose-400 font-bold">-</button>
                        <span class="font-bold px-1">${item.qty}</span>
                        <button onclick="changeCartQty(${idx}, 1)" class="w-6 h-6 bg-slate-800 rounded-lg text-emerald-400 font-bold">+</button>
                    </div>
                </div>
            `;
        }).join('');

        const finalTotal = Math.max(0, subtotal - discount);
        document.getElementById('cart-total').innerText = finalTotal.toFixed(2) + ' DH';
    }

    async function checkout(method) {
        if (cart.length === 0) {
            Swal.fire('السلة خاوية', 'زيد السلعة للسلة بعدا عاد دير الخلاص', 'warning');
            return;
        }

        const discount = parseFloat(document.getElementById('cart-discount').value) || 0;
        let customerId = null;
        let customerName = 'زبون عابر';

        if (method === 'CREDIT') {
            const options = {};
            allCustomers.forEach(c => { options[c.id] = `${c.name} (كريدي: ${c.debt.toFixed(2)} DH)`; });

            const { value: selectedId } = await Swal.fire({
                title: 'ختار الزبون (الكناش)',
                input: 'select',
                inputOptions: options,
                inputPlaceholder: '-- ختار زبون مسجل --',
                showCancelButton: true,
                confirmButtonText: 'تسجيل الكريدي',
                footer: '<button onclick="Swal.close(); openCustomerModal();" class="text-sky-400 underline text-xs">+ إضافة زبون جديد للكناش</button>'
            });

            if (!selectedId) return;
            customerId = selectedId;
            const cust = allCustomers.find(c => c.id == selectedId);
            if (cust) customerName = cust.name;
        }

        fetch('/api/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cart, discount, payment_method: method, customer_id: customerId, customer_name: customerName })
        })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                playBeep();
                const soldCart = [...cart];
                const totalPaid = res.total_amount;
                clearCart();
                loadData();

                Swal.fire({
                    title: '✅ دازت المبيعة بنجاح!',
                    html: `المجموع: <b class="text-emerald-400">${totalPaid.toFixed(2)} DH</b> (${method === 'CASH' ? 'كاش' : 'كريدي على ' + customerName})`,
                    icon: 'success',
                    showCancelButton: true,
                    confirmButtonColor: '#10b981',
                    confirmButtonText: '<i class="fa-brands fa-whatsapp"></i> صيفط التوصيل فـ WhatsApp',
                    cancelButtonText: 'سد'
                }).then(r => {
                    if (r.isConfirmed) sendReceiptWhatsApp(soldCart, totalPaid, discount, customerName, method);
                });
            }
        });
    }

    function sendReceiptWhatsApp(items, total, discount, customerName, method) {
        let lines = items.map(i => `▪️ ${i.name} (${i.qty}x) : ${(i.sell_price * i.qty).toFixed(2)} DH`).join('%0A');
        let msg = `🧾 *توصيل المبيعات - MAHAAL PRO*%0A👤 الزبون: ${customerName}%0A-----------------%0A${lines}%0A-----------------%0A`;
        if (discount > 0) msg += `🎁 تخفيض: -${discount.toFixed(2)} DH%0A`;
        msg += `💰 *المجموع: ${total.toFixed(2)} DH* (${method === 'CASH' ? 'خالص كاش' : 'مقيد كريدي'})%0Aشكراً على ثقتكم! 🙏`;
        window.open(`https://wa.me/?text=${msg}`, '_blank');
    }

    // ================ BARCODE STICKER PRINTER ================
    function printBarcodeSticker(p) {
        if (!p) return;
        Swal.fire({
            title: p.name,
            html: `
                <div id="print-area" class="bg-white text-black p-4 rounded-xl inline-block text-center">
                    <div style="font-weight:900; font-size:15px; margin-bottom:2px;">${p.name}</div>
                    <svg id="barcode-svg"></svg>
                    <div style="font-weight:900; font-size:18px; margin-top:2px;">${p.sell_price.toFixed(2)} DH</div>
                </div>
            `,
            didOpen: () => {
                JsBarcode("#barcode-svg", p.barcode, { format: "CODE128", width: 2, height: 50, displayValue: true, fontSize: 13 });
            },
            showCancelButton: true,
            confirmButtonText: '<i class="fa-solid fa-print"></i> طباعة التيكيت',
            cancelButtonText: 'إغلاق'
        }).then(res => {
            if (res.isConfirmed) {
                const content = document.getElementById('print-area').outerHTML;
                const win = window.open('', '', 'width=400,height=300');
                win.document.write(`<html><body style="text-align:center; padding:20px;">${content}<script>window.onload=function(){window.print();window.close();}<\/script></body></html>`);
                win.document.close();
            }
        });
    }

    // ================ KONNACH CUSTOMERS & CREDIT ================
    async function openCustomerModal() {
        const { value: formValues } = await Swal.fire({
            title: 'إضافة زبون لـ كناش الكريدي',
            html: `
                <input id="swal-cust-name" class="swal2-input" placeholder="سمية الزبون">
                <input id="swal-cust-phone" class="swal2-input" placeholder="رقم التليفون (مثال: 0612345678)">
                <input id="swal-cust-debt" type="number" step="0.01" class="swal2-input" placeholder="كريدي قديم (اختياري DH)" value="0">
            `,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: 'حفظ الزبون',
            preConfirm: () => {
                return {
                    name: document.getElementById('swal-cust-name').value.trim(),
                    phone: document.getElementById('swal-cust-phone').value.trim(),
                    debt: parseFloat(document.getElementById('swal-cust-debt').value) || 0
                };
            }
        });

        if (formValues && formValues.name) {
            fetch('/api/customers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formValues)
            }).then(() => loadData());
        }
    }

    async function adjustCustomerDebt(cid, name, action) {
        const title = action === 'pay' ? `شحال خلصك ${name}؟` : `شحال بغيتي تزيد فـ كريدي ${name}؟`;
        const { value: amount } = await Swal.fire({
            title: title,
            input: 'number',
            inputAttributes: { step: '0.01', min: '1' },
            showCancelButton: true,
            confirmButtonText: 'تأكيد'
        });

        if (amount && parseFloat(amount) > 0) {
            fetch('/api/customer_debt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: cid, amount: parseFloat(amount), action })
            }).then(() => {
                playBeep();
                loadData();
            });
        }
    }

    function remindWhatsApp(name, phone, debt) {
        let cleanPhone = (phone || '').replace(/\s+/g, '');
        if (cleanPhone.startsWith('0')) cleanPhone = '212' + cleanPhone.substring(1);
        const msg = `السلام عليكم سي ${name}، نتمنى تكون بخير وعلى خير 🙏%0Aغير تذكير ودي بخصوص الحساب ديالكم فـ المحل، المبلغ المتبقي هو: *${debt.toFixed(2)} DH*.%0Aبارك الله فيك ونهارك مبروك!`;
        window.open(`https://wa.me/${cleanPhone}?text=${msg}`, '_blank');
    }

    // ================ EXPENSES & BACKUP ================
    function addExpense(e) {
        e.preventDefault();
        const title = document.getElementById('exp-title').value.trim();
        const amount = parseFloat(document.getElementById('exp-amount').value) || 0;
        fetch('/api/expenses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, amount })
        }).then(() => {
            document.getElementById('exp-title').value = '';
            document.getElementById('exp-amount').value = '';
            loadData();
        });
    }

    function restoreBackup(input) {
        if (!input.files.length) return;
        const reader = new FileReader();
        reader.onload = function(e) {
            fetch('/api/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: e.target.result
            }).then(r => r.json()).then(res => {
                if (res.success) {
                    Swal.fire('تم الاسترجاع!', 'رجعات كاع الداتا ديالك بنجاح', 'success');
                    loadData();
                }
            });
        };
        reader.readAsText(input.files[0]);
    }

    // ================ PRODUCT FUNCTIONS ================
    function showProductCard(p) {
        document.getElementById('scan-result').classList.remove('hidden');
        document.getElementById('res-name').innerText = p.name;
        document.getElementById('res-cat').innerText = p.category;
        document.getElementById('res-code').innerText = '#' + p.barcode;
        document.getElementById('res-buy').innerText = p.buy_price.toFixed(2) + ' DH';
        document.getElementById('res-sell').innerText = p.sell_price.toFixed(2) + ' DH';
        document.getElementById('res-profit').innerText = '+' + (p.sell_price - p.buy_price).toFixed(2) + ' DH';
        document.getElementById('res-qty').innerText = p.quantity;
    }

    function quickAdjust(action) {
        if (!currentProduct) return;
        const qty = parseInt(document.getElementById('quick-qty').value) || 1;
        updateStockAPI(currentProduct.barcode, qty, action);
    }

    function updateStockAPI(barcode, amount, action) {
        fetch('/api/stock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ barcode, amount, action })
        }).then(r => r.json()).then(data => {
            if (data.success) {
                Swal.fire({ toast: true, position: 'top', timer: 1300, showConfirmButton: false, icon: 'success', title: data.message });
                loadData(barcode);
            }
        });
    }

    function openAddModal(barcode = '') {
        document.getElementById('product-form').reset();
        document.getElementById('form-barcode').value = barcode;
        document.getElementById('product-modal').classList.remove('hidden');
    }

    function editCurrentProduct() {
        if (!currentProduct) return;
        document.getElementById('form-barcode').value = currentProduct.barcode;
        document.getElementById('form-name').value = currentProduct.name;
        document.getElementById('form-cat').value = currentProduct.category;
        document.getElementById('form-buy').value = currentProduct.buy_price;
        document.getElementById('form-sell').value = currentProduct.sell_price;
        document.getElementById('form-qty').value = currentProduct.quantity;
        document.getElementById('form-min').value = currentProduct.min_stock;
        document.getElementById('product-modal').classList.remove('hidden');
    }

    function closeModal() { document.getElementById('product-modal').classList.add('hidden'); }

    function generateBarcode() {
        document.getElementById('form-barcode').value = '611' + Math.floor(100000000 + Math.random() * 900000000);
    }

    function saveProduct(e) {
        e.preventDefault();
        const payload = {
            barcode: document.getElementById('form-barcode').value.trim(),
            name: document.getElementById('form-name').value.trim(),
            category: document.getElementById('form-cat').value.trim(),
            buy_price: parseFloat(document.getElementById('form-buy').value) || 0,
            sell_price: parseFloat(document.getElementById('form-sell').value) || 0,
            quantity: parseInt(document.getElementById('form-qty').value) || 0,
            min_stock: parseInt(document.getElementById('form-min').value) || 3
        };
        fetch('/api/save_product', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(() => {
            closeModal();
            playBeep();
            loadData(payload.barcode);
        });
    }

    function deleteProduct(id) {
        Swal.fire({
            title: 'مسح السلعة؟', icon: 'warning', showCancelButton: true,
            confirmButtonColor: '#ef4444', confirmButtonText: 'نعم، مسحها', cancelButtonText: 'لا'
        }).then(res => {
            if (res.isConfirmed) fetch('/api/delete/' + id, { method: 'DELETE' }).then(() => loadData());
        });
    }

    function loadData(focusBarcode = null) {
        fetch('/api/data')
            .then(r => r.json())
            .then(data => {
                allProducts = data.products;
                allCustomers = data.customers;

                document.getElementById('nav-count').innerText = allProducts.length;
                document.getElementById('stat-items').innerText = data.stats.total_items;
                document.getElementById('stat-capital').innerText = data.stats.total_capital.toFixed(2) + ' DH';
                document.getElementById('stat-profit').innerText = '+' + data.stats.total_profit.toFixed(2) + ' DH';

                document.getElementById('stat-sales-today').innerText = data.stats.sales_today.toFixed(2) + ' DH';
                document.getElementById('stat-real-profit').innerText = '+' + data.stats.real_profit.toFixed(2) + ' DH';
                document.getElementById('stat-expenses').innerText = '-' + data.stats.total_expenses.toFixed(2) + ' DH';
                document.getElementById('stat-net-cash').innerText = (data.stats.real_profit - data.stats.total_expenses).toFixed(2) + ' DH';
                document.getElementById('total-credit-stat').innerText = data.stats.total_credit.toFixed(2) + ' DH';

                renderProducts();
                renderCustomers();
                renderLowStock();
                renderExpenses(data.expenses);
                renderSales(data.sales);
                renderHistory(data.movements);

                if (focusBarcode) {
                    const updated = allProducts.find(p => p.barcode === focusBarcode);
                    if (updated) { currentProduct = updated; showProductCard(updated); }
                }
            });
    }

    function renderProducts() {
        const q = (document.getElementById('search-input').value || '').toLowerCase();
        const container = document.getElementById('products-list');
        const filtered = allProducts.filter(p => p.name.toLowerCase().includes(q) || p.barcode.includes(q) || p.category.toLowerCase().includes(q));

        if (filtered.length === 0) {
            container.innerHTML = `<div class="glass p-6 rounded-2xl text-center text-slate-400 text-xs">ما كاينة حتى سلعة.</div>`;
            return;
        }

        container.innerHTML = filtered.map(p => `
            <div onclick="selectFromList('${p.barcode}')" class="glass p-3 rounded-2xl flex justify-between items-center cursor-pointer hover:border-sky-500/40">
                <div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-[10px] bg-slate-800 text-sky-400 px-2 py-0.5 rounded">${p.category}</span>
                        <code class="text-[11px] text-slate-400">#${p.barcode}</code>
                    </div>
                    <h4 class="font-bold text-sm text-white mt-0.5">${p.name}</h4>
                    <div class="flex gap-3 mt-0.5 text-xs">
                        <span class="text-amber-400">شراء: <b>${p.buy_price.toFixed(2)}</b></span>
                        <span class="text-emerald-400">بيع: <b>${p.sell_price.toFixed(2)} DH</b></span>
                    </div>
                </div>
                <div class="flex flex-col items-end gap-1.5">
                    <span class="px-2.5 py-0.5 rounded-xl font-black text-xs ${p.quantity <= p.min_stock ? 'bg-rose-500/20 text-rose-400' : 'bg-emerald-500/20 text-emerald-400'}">
                        ${p.quantity} فـ الستوك
                    </span>
                    <div class="flex gap-2">
                        <button onclick="event.stopPropagation(); addToCart(${JSON.stringify(p).replace(/"/g, '&quot;')}, 1)" class="bg-sky-500/20 text-sky-400 px-2 py-1 rounded-lg text-xs">
                            <i class="fa-solid fa-cart-plus"></i>
                        </button>
                        <button onclick="event.stopPropagation(); printBarcodeSticker(${JSON.stringify(p).replace(/"/g, '&quot;')})" class="bg-amber-500/20 text-amber-400 px-2 py-1 rounded-lg text-xs">
                            <i class="fa-solid fa-print"></i>
                        </button>
                        <button onclick="event.stopPropagation(); deleteProduct(${p.id})" class="text-slate-500 hover:text-rose-400 px-1 text-xs">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    function renderCustomers() {
        const box = document.getElementById('customers-list');
        if (allCustomers.length === 0) {
            box.innerHTML = `<div class="glass p-6 rounded-2xl text-center text-slate-400">ما مسجل حتى زبون فـ الكناش.</div>`;
            return;
        }
        box.innerHTML = allCustomers.map(c => `
            <div class="glass p-3.5 rounded-2xl flex justify-between items-center">
                <div>
                    <h4 class="font-black text-sm text-white">${c.name}</h4>
                    <span class="text-[11px] text-slate-400"><i class="fa-solid fa-phone"></i> ${c.phone || 'بدون رقم'}</span>
                    <div class="mt-1 text-amber-400 font-black text-sm">الكريدي: ${c.debt.toFixed(2)} DH</div>
                </div>
                <div class="flex flex-col gap-1.5">
                    <div class="flex gap-1">
                        <button onclick="adjustCustomerDebt(${c.id}, '${c.name}', 'pay')" class="bg-emerald-500 text-slate-950 font-bold px-2.5 py-1.5 rounded-xl text-[11px]">
                            💵 خلّص
                        </button>
                        <button onclick="adjustCustomerDebt(${c.id}, '${c.name}', 'add')" class="bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold px-2.5 py-1.5 rounded-xl text-[11px]">
                            + كريدي
                        </button>
                    </div>
                    <button onclick="remindWhatsApp('${c.name}', '${c.phone}', ${c.debt})" class="bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 py-1 rounded-xl text-[11px] font-bold flex items-center justify-center gap-1">
                        <i class="fa-brands fa-whatsapp"></i> تذكير فـ واتساب
                    </button>
                </div>
            </div>
        `).join('');
    }

    function selectFromList(barcode) {
        document.querySelectorAll('.fixed.bottom-0 button')[0].click();
        currentProduct = allProducts.find(p => p.barcode === barcode);
        if (currentProduct) showProductCard(currentProduct);
    }

    function renderLowStock() {
        const low = allProducts.filter(p => p.quantity <= p.min_stock);
        const box = document.getElementById('low-stock-list');
        if (low.length === 0) {
            box.innerHTML = `<p class="text-emerald-400">✅ كاع السلعة متوفرة بكمية كافية!</p>`;
            return;
        }
        box.innerHTML = low.map(p => `
            <div class="bg-rose-500/10 border border-rose-500/20 p-2 rounded-xl flex justify-between items-center">
                <span><b>${p.name}</b> (#${p.barcode})</span>
                <span class="bg-rose-500 text-white px-2 py-0.5 rounded-lg font-bold">بقات ${p.quantity}</span>
            </div>
        `).join('');
    }

    function renderExpenses(exps) {
        const box = document.getElementById('expenses-list');
        if (!exps || exps.length === 0) { box.innerHTML = ''; return; }
        box.innerHTML = exps.map(x => `
            <div class="flex justify-between items-center bg-slate-900/80 px-2.5 py-1.5 rounded-lg">
                <span>${x.title} <small class="text-slate-500">(${x.created_at})</small></span>
                <b class="text-rose-400">-${x.amount.toFixed(2)} DH</b>
            </div>
        `).join('');
    }

    function renderSales(sales) {
        const box = document.getElementById('sales-list');
        if (!sales || sales.length === 0) {
            box.innerHTML = `<p class="text-slate-400">مازال ما دازت حتى مبيعة.</p>`;
            return;
        }
        box.innerHTML = sales.map(s => `
            <div class="bg-slate-900/90 p-2.5 rounded-xl flex justify-between items-center border border-slate-800">
                <div>
                    <b class="text-white">${s.customer_name}</b>
                    <span class="text-[10px] px-1.5 py-0.5 rounded mr-1 ${s.payment_method === 'CASH' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}">${s.payment_method}</span>
                    <span class="block text-[10px] text-slate-400 mt-0.5">${s.created_at}</span>
                </div>
                <div class="text-left">
                    <b class="text-emerald-400 block">${s.total_amount.toFixed(2)} DH</b>
                    <small class="text-sky-400 text-[10px]">الربح: +${s.total_profit.toFixed(2)} DH</small>
                </div>
            </div>
        `).join('');
    }

    function renderHistory(moves) {
        const box = document.getElementById('history-list');
        if (!moves || moves.length === 0) {
            box.innerHTML = `<p class="text-slate-400">مازال ما كاين حتى تحرك.</p>`;
            return;
        }
        box.innerHTML = moves.map(m => `
            <div class="bg-slate-900/80 p-2 rounded-xl flex justify-between items-center border border-slate-800">
                <div>
                    <b class="text-white block">${m.product_name}</b>
                    <span class="text-[10px] text-slate-400">${m.created_at}</span>
                </div>
                <span class="font-bold px-2 py-0.5 rounded-lg ${m.move_type === 'IN' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">
                    ${m.move_type === 'IN' ? '+' + m.qty : '-' + m.qty}
                </span>
            </div>
        `).join('');
    }

    loadData();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    init_db()
    return Response(HTML_PAGE, mimetype="text/html")

@app.route("/api/data")
def get_data():
    init_db()
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM products ORDER BY id DESC")
        products = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM customers ORDER BY debt DESC, id DESC")
        customers = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 30")
        sales = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 25")
        expenses = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM movements ORDER BY id DESC LIMIT 35")
        moves = [dict(r) for r in c.fetchall()]

        c.execute("SELECT SUM(total_amount), SUM(total_profit) FROM sales")
        s_row = c.fetchone()
        real_profit = s_row[1] or 0.0

        c.execute("SELECT SUM(total_amount) FROM sales WHERE created_at LIKE ?", (today_prefix + "%",))
        sales_today = c.fetchone()[0] or 0.0

        c.execute("SELECT SUM(amount) FROM expenses")
        total_expenses = c.fetchone()[0] or 0.0

    total_items = sum(p["quantity"] for p in products)
    total_capital = sum(p["quantity"] * p["buy_price"] for p in products)
    total_profit = sum(p["quantity"] * (p["sell_price"] - p["buy_price"]) for p in products)
    total_credit = sum(cust["debt"] for cust in customers)

    return jsonify({
        "products": products,
        "customers": customers,
        "sales": sales,
        "expenses": expenses,
        "movements": moves,
        "stats": {
            "total_items": total_items,
            "total_capital": total_capital,
            "total_profit": total_profit,
            "sales_today": sales_today,
            "real_profit": real_profit,
            "total_expenses": total_expenses,
            "total_credit": total_credit
        }
    })

@app.route("/api/checkout", methods=["POST"])
def checkout_pos():
    init_db()
    d = request.json
    cart = d.get("cart", [])
    discount = float(d.get("discount", 0))
    method = d.get("payment_method", "CASH")
    customer_id = d.get("customer_id")
    customer_name = d.get("customer_name", "زبون عابر")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    subtotal = sum(item["sell_price"] * item["qty"] for item in cart)
    raw_profit = sum((item["sell_price"] - item["buy_price"]) * item["qty"] for item in cart)
    total_amount = max(0.0, subtotal - discount)
    total_profit = raw_profit - discount

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        for item in cart:
            c.execute("SELECT quantity FROM products WHERE barcode = ?", (item["barcode"],))
            row = c.fetchone()
            if row:
                new_q = max(0, row[0] - int(item["qty"]))
                c.execute("UPDATE products SET quantity = ? WHERE barcode = ?", (new_q, item["barcode"]))
                c.execute("INSERT INTO movements (barcode, product_name, move_type, qty, created_at) VALUES (?, ?, 'OUT', ?, ?)",
                          (item["barcode"], item["name"], int(item["qty"]), now))

        c.execute('''
            INSERT INTO sales (items_json, total_amount, total_profit, discount, payment_method, customer_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (json.dumps(cart, ensure_ascii=False), total_amount, total_profit, discount, method, customer_name, now))

        if method == "CREDIT" and customer_id:
            c.execute("UPDATE customers SET debt = debt + ? WHERE id = ?", (total_amount, customer_id))

        conn.commit()

    return jsonify({"success": True, "total_amount": total_amount})

@app.route("/api/customers", methods=["POST"])
def add_customer():
    init_db()
    d = request.json
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO customers (name, phone, debt) VALUES (?, ?, ?)",
                  (d.get("name"), d.get("phone", ""), float(d.get("debt", 0))))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/customer_debt", methods=["POST"])
def customer_debt():
    init_db()
    d = request.json
    cid = d.get("id")
    amount = float(d.get("amount", 0))
    action = d.get("action")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if action == "pay":
            c.execute("UPDATE customers SET debt = MAX(0, debt - ?) WHERE id = ?", (amount, cid))
        else:
            c.execute("UPDATE customers SET debt = debt + ? WHERE id = ?", (amount, cid))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/expenses", methods=["POST"])
def add_expense():
    init_db()
    d = request.json
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO expenses (title, amount, created_at) VALUES (?, ?, ?)",
                  (d.get("title"), float(d.get("amount", 0)), now))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/save_product", methods=["POST"])
def save_product():
    init_db()
    d = request.json
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE barcode = ?", (d["barcode"],))
        if c.fetchone():
            c.execute('''
                UPDATE products SET name=?, category=?, buy_price=?, sell_price=?, quantity=?, min_stock=?
                WHERE barcode=?
            ''', (d["name"], d["category"], d["buy_price"], d["sell_price"], d["quantity"], d["min_stock"], d["barcode"]))
        else:
            c.execute('''
                INSERT INTO products (barcode, name, category, buy_price, sell_price, quantity, min_stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (d["barcode"], d["name"], d["category"], d["buy_price"], d["sell_price"], d["quantity"], d["min_stock"]))
            c.execute("INSERT INTO movements (barcode, product_name, move_type, qty, created_at) VALUES (?, ?, 'IN', ?, ?)",
                      (d["barcode"], d["name"], d["quantity"], now))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/stock", methods=["POST"])
def adjust_stock():
    init_db()
    d = request.json
    barcode = d.get("barcode")
    amount = int(d.get("amount", 1))
    action = d.get("action")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, quantity FROM products WHERE barcode = ?", (barcode,))
        row = c.fetchone()
        if not row:
            return jsonify({"success": False}), 404
        name, current_qty = row
        new_qty = current_qty + amount if action == "add" else max(0, current_qty - amount)
        move_type = "IN" if action == "add" else "OUT"

        c.execute("UPDATE products SET quantity = ? WHERE barcode = ?", (new_qty, barcode))
        c.execute("INSERT INTO movements (barcode, product_name, move_type, qty, created_at) VALUES (?, ?, ?, ?, ?)",
                  (barcode, name, move_type, amount, now))
        conn.commit()

    msg = f"تزادو {amount} فـ {name} (الستوك: {new_qty})" if action == "add" else f"خرجو {amount} من {name} (الستوك: {new_qty})"
    return jsonify({"success": True, "message": msg})

@app.route("/api/delete/<int:pid>", methods=["DELETE"])
def delete_prod(pid):
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id = ?", (pid,))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/backup")
def backup_db():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        data = {
            "products": [dict(r) for r in c.execute("SELECT * FROM products").fetchall()],
            "customers": [dict(r) for r in c.execute("SELECT * FROM customers").fetchall()],
            "sales": [dict(r) for r in c.execute("SELECT * FROM sales").fetchall()],
            "expenses": [dict(r) for r in c.execute("SELECT * FROM expenses").fetchall()]
        }
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=mahaal_backup.json"}
    )

@app.route("/api/restore", methods=["POST"])
def restore_db():
    init_db()
    data = request.json
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        for p in data.get("products", []):
            c.execute('''
                INSERT OR REPLACE INTO products (barcode, name, category, quantity, min_stock, buy_price, sell_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (p["barcode"], p["name"], p.get("category", "عام"), p["quantity"], p.get("min_stock", 3), p["buy_price"], p["sell_price"]))
        for cust in data.get("customers", []):
            c.execute("INSERT INTO customers (name, phone, debt) VALUES (?, ?, ?)",
                      (cust["name"], cust.get("phone", ""), cust.get("debt", 0)))
        conn.commit()
    return jsonify({"success": True})

@app.route("/export_csv")
def export_csv():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT barcode, name, category, quantity, buy_price, sell_price FROM products")
        rows = c.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Code-Barres", "Produit", "Categorie", "Quantite", "Prix Achat (DH)", "Prix Vente (DH)"])
    writer.writerows(rows)

    return Response(
        output.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=stock_mahaal.csv"}
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
