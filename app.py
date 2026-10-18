from flask import Flask, request, render_template_string, jsonify, Response
import sqlite3
import os
import csv
import io
from datetime import datetime

app = Flask(__name__)
DB_NAME = os.path.join("/tmp", "warehouse_v2.db") if os.name != "nt" else "warehouse_v2.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Général',
                quantity INTEGER DEFAULT 0,
                min_stock INTEGER DEFAULT 3,
                buy_price REAL DEFAULT 0.0,
                sell_price REAL DEFAULT 0.0
            )
        ''')
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

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Warehouse Pro V2</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
        body { font-family: 'Cairo', sans-serif; background-color: #0f172a; color: #f8fafc; padding-bottom: 85px; }
        .glass { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); }
        .nav-active { color: #38bdf8 !important; transform: translateY(-3px); }
        #reader video { border-radius: 16px; object-fit: cover; }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.2s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>

    <!-- Top Bar -->
    <div class="glass sticky top-0 z-40 px-4 py-3 flex justify-between items-center shadow-lg">
        <div class="flex items-center gap-2">
            <div class="bg-sky-500 p-2 rounded-xl text-slate-950 font-black">
                <i class="fa-solid fa-boxes-stacked text-lg"></i>
            </div>
            <div>
                <h1 class="font-bold text-base leading-none">Warehouse PRO</h1>
                <span class="text-xs text-emerald-400 flex items-center gap-1 mt-0.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span> متصل بالنظام
                </span>
            </div>
        </div>
        <div class="flex gap-2">
            <a href="/export_csv" class="bg-slate-800 hover:bg-slate-700 text-xs px-3 py-2 rounded-xl border border-slate-700 flex items-center gap-1">
                <i class="fa-solid fa-file-excel text-emerald-400"></i> Excel
            </a>
            <button onclick="openAddModal()" class="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs px-3 py-2 rounded-xl flex items-center gap-1">
                <i class="fa-solid fa-plus"></i> سلعة جديدة
            </button>
        </div>
    </div>

    <div class="max-w-lg mx-auto px-3 pt-4">

        <!-- TAB 1: SCANNER PRO (Default) -->
        <div id="tab-scan" class="tab-content active">
            <!-- Mode Selector -->
            <div class="glass rounded-2xl p-1.5 mb-3 grid grid-cols-3 gap-1 text-center text-xs font-bold">
                <button onclick="setScanMode('info')" id="mode-info" class="py-2.5 rounded-xl bg-sky-500 text-slate-950 transition">
                    <i class="fa-solid fa-magnifying-glass block mb-1 text-sm"></i> كشف الثمن والستوك
                </button>
                <button onclick="setScanMode('out')" id="mode-out" class="py-2.5 rounded-xl text-slate-300 transition">
                    <i class="fa-solid fa-cart-arrow-down block mb-1 text-sm text-rose-400"></i> إخراج مباشر (-1)
                </button>
                <button onclick="setScanMode('in')" id="mode-in" class="py-2.5 rounded-xl text-slate-300 transition">
                    <i class="fa-solid fa-truck-ramp-box block mb-1 text-sm text-emerald-400"></i> إدخال مباشر (+1)
                </button>
            </div>

            <!-- Camera Box -->
            <div class="glass rounded-2xl p-4 mb-4 text-center relative overflow-hidden">
                <div id="scanner-placeholder" class="py-8">
                    <div class="w-16 h-16 bg-sky-500/10 border border-sky-500/30 rounded-full flex items-center justify-center mx-auto mb-3 text-sky-400 text-2xl">
                        <i class="fa-solid fa-barcode"></i>
                    </div>
                    <h3 class="font-bold text-sm mb-1">سكانير الكود-بار الذكي</h3>
                    <p class="text-xs text-slate-400 mb-4">وجه الكاميرا للكود-بار باش تعرف الثمن والستوك فـ البلاصة</p>
                    <div class="flex justify-center gap-2">
                        <button onclick="startCamera()" class="bg-sky-500 text-slate-950 font-bold px-6 py-3 rounded-xl shadow-lg shadow-sky-500/20 flex items-center gap-2">
                            <i class="fa-solid fa-camera"></i> شغّل الكاميرا دابا
                        </button>
                        <label class="bg-slate-800 border border-slate-700 text-slate-200 font-bold px-4 py-3 rounded-xl cursor-pointer flex items-center gap-2">
                            <i class="fa-solid fa-image text-amber-400"></i> صوّر الكود
                            <input type="file" accept="image/*" capture="environment" class="hidden" onchange="scanFromFile(this)">
                        </label>
                    </div>
                </div>

                <div id="reader" class="w-full hidden"></div>

                <div id="camera-controls" class="hidden mt-3 flex justify-center gap-2">
                    <button onclick="toggleTorch()" id="torch-btn" class="bg-amber-500/20 border border-amber-500/40 text-amber-300 px-4 py-2 rounded-xl text-xs font-bold">
                        <i class="fa-solid fa-bolt"></i> الفلاش (Flash)
                    </button>
                    <button onclick="stopCamera()" class="bg-rose-500/20 border border-rose-500/40 text-rose-300 px-4 py-2 rounded-xl text-xs font-bold">
                        <i class="fa-solid fa-stop"></i> إيقاف الكاميرا
                    </button>
                </div>

                <!-- Manual Barcode Search -->
                <div class="mt-4 pt-3 border-t border-slate-800 flex gap-2">
                    <input type="text" id="manual-barcode" placeholder="أولا كتب رقم الكود-بار هنا..." 
                        class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-sky-500"
                        onkeypress="if(event.key === 'Enter') handleBarcode(this.value)">
                    <button onclick="handleBarcode(document.getElementById('manual-barcode').value)" class="bg-slate-800 px-4 rounded-xl text-sky-400 border border-slate-700">
                        <i class="fa-solid fa-search"></i>
                    </button>
                </div>
            </div>

            <!-- Scanned Product Result Card -->
            <div id="scan-result" class="hidden glass rounded-2xl p-4 border-r-4 border-sky-500 mb-4">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <span id="res-cat" class="text-[11px] bg-sky-500/20 text-sky-300 px-2 py-0.5 rounded-md"></span>
                        <h2 id="res-name" class="text-lg font-extrabold text-white mt-1"></h2>
                        <code id="res-code" class="text-xs text-slate-400"></code>
                    </div>
                    <button onclick="editCurrentProduct()" class="text-slate-400 hover:text-white bg-slate-800 p-2 rounded-lg text-xs">
                        <i class="fa-solid fa-pen"></i> تعديل
                    </button>
                </div>

                <div class="grid grid-cols-2 gap-2.5 text-center mb-4">
                    <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-800">
                        <span class="text-xs text-slate-400 block">بشحال شريتو (الشراء)</span>
                        <strong id="res-buy" class="text-base font-bold text-amber-400">0.00 DH</strong>
                    </div>
                    <div class="bg-emerald-500/10 p-3 rounded-xl border border-emerald-500/30">
                        <span class="text-xs text-emerald-300 block">بشحال نبيعو (البيع)</span>
                        <strong id="res-sell" class="text-lg font-black text-emerald-400">0.00 DH</strong>
                    </div>
                    <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-800">
                        <span class="text-xs text-slate-400 block">الربح الصافي فـ الحبة</span>
                        <strong id="res-profit" class="text-base font-bold text-sky-400">+0.00 DH</strong>
                    </div>
                    <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-800">
                        <span class="text-xs text-slate-400 block">شحال باقي فـ الستوك</span>
                        <strong id="res-qty" class="text-xl font-black text-white">0</strong>
                    </div>
                </div>

                <!-- Quick Stock Adjust -->
                <div class="flex items-center gap-2">
                    <input type="number" id="quick-qty" value="1" min="1" class="w-20 bg-slate-900 border border-slate-700 rounded-xl py-2.5 text-center font-bold">
                    <button onclick="quickAdjust('add')" class="flex-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2.5 rounded-xl flex items-center justify-center gap-1">
                        <i class="fa-solid fa-plus"></i> زيد للستوك
                    </button>
                    <button onclick="quickAdjust('remove')" class="flex-1 bg-rose-500 hover:bg-rose-400 text-white font-bold py-2.5 rounded-xl flex items-center justify-center gap-1">
                        <i class="fa-solid fa-minus"></i> خرج من الستوك
                    </button>
                </div>
            </div>
        </div>

        <!-- TAB 2: DASHBOARD -->
        <div id="tab-dash" class="tab-content">
            <div class="grid grid-cols-2 gap-3 mb-4">
                <div class="glass p-4 rounded-2xl border-r-4 border-sky-500">
                    <span class="text-xs text-slate-400">مجموع القطع فـ الديبو</span>
                    <h3 id="stat-items" class="text-2xl font-black mt-1">0</h3>
                </div>
                <div class="glass p-4 rounded-2xl border-r-4 border-amber-500">
                    <span class="text-xs text-slate-400">راس المال (ثمن الشراء)</span>
                    <h3 id="stat-capital" class="text-xl font-black text-amber-400 mt-1">0 DH</h3>
                </div>
                <div class="glass p-4 rounded-2xl border-r-4 border-emerald-500 col-span-2 flex justify-between items-center">
                    <div>
                        <span class="text-xs text-slate-400">الربح الصافي المتوقع من الستوك</span>
                        <h3 id="stat-profit" class="text-2xl font-black text-emerald-400 mt-1">+0.00 DH</h3>
                    </div>
                    <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-emerald-400 text-xl">
                        <i class="fa-solid fa-sack-dollar"></i>
                    </div>
                </div>
            </div>

            <div class="glass rounded-2xl p-4 mb-4">
                <h4 class="font-bold text-sm mb-3 flex items-center gap-2 text-rose-400">
                    <i class="fa-solid fa-triangle-exclamation"></i> تنبيهات سلعة قربات تسالي (Stock Faible)
                </h4>
                <div id="low-stock-list" class="space-y-2 text-xs"></div>
            </div>
        </div>

        <!-- TAB 3: PRODUCTS LIST -->
        <div id="tab-products" class="tab-content">
            <div class="glass rounded-2xl p-3 mb-3 flex gap-2">
                <input type="text" id="search-input" oninput="renderProducts()" placeholder="🔍 قلب بالسمية، الكود، أو الصنف..." 
                    class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500">
            </div>
            <div id="products-list" class="space-y-2.5"></div>
        </div>

        <!-- TAB 4: HISTORY -->
        <div id="tab-history" class="tab-content">
            <div class="glass rounded-2xl p-4">
                <h4 class="font-bold text-sm mb-3 flex items-center gap-2">
                    <i class="fa-solid fa-clock-rotate-left text-sky-400"></i> آخر التحركات (الدخلة والخرجة)
                </h4>
                <div id="history-list" class="space-y-2 text-xs"></div>
            </div>
        </div>

    </div>

    <!-- Modal Add / Edit Product -->
    <div id="product-modal" class="fixed inset-0 bg-black/80 z-50 hidden flex items-center justify-center p-4">
        <div class="glass w-full max-w-md rounded-2xl p-5 border border-slate-700">
            <div class="flex justify-between items-center mb-4">
                <h3 id="modal-title" class="font-bold text-base">إضافة / تعديل سلعة</h3>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <form id="product-form" onsubmit="saveProduct(event)" class="space-y-3 text-xs">
                <div>
                    <label class="block text-slate-300 mb-1">الكود-بار (Code-Barres)</label>
                    <div class="flex gap-2">
                        <input type="text" id="form-barcode" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white">
                        <button type="button" onclick="generateBarcode()" class="bg-slate-800 border border-slate-700 px-3 rounded-xl text-sky-400 whitespace-nowrap">
                            <i class="fa-solid fa-wand-magic-sparkles"></i> توليد كود
                        </button>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-slate-300 mb-1">سمية السلعة</label>
                        <input type="text" id="form-name" required placeholder="مثلاً: كابل أيفون" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white">
                    </div>
                    <div>
                        <label class="block text-slate-300 mb-1">الصنف (Catégorie)</label>
                        <input type="text" id="form-cat" value="عام" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-amber-400 mb-1 font-bold">بشحال شريتيه (DH)</label>
                        <input type="number" step="0.01" id="form-buy" required class="w-full bg-slate-900 border border-amber-500/40 rounded-xl px-3 py-2.5 text-white">
                    </div>
                    <div>
                        <label class="block text-emerald-400 mb-1 font-bold">بشحال تبيعو (DH)</label>
                        <input type="number" step="0.01" id="form-sell" required class="w-full bg-slate-900 border border-emerald-500/40 rounded-xl px-3 py-2.5 text-white">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-slate-300 mb-1">الكمية فـ الستوك</label>
                        <input type="number" id="form-qty" value="1" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white">
                    </div>
                    <div>
                        <label class="block text-slate-300 mb-1">تنبيه إيلا هبط على</label>
                        <input type="number" id="form-min" value="3" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white">
                    </div>
                </div>
                <button type="submit" class="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-black py-3 rounded-xl mt-2">
                    💾 حفظ السلعة فـ الديبو
                </button>
            </form>
        </div>
    </div>

    <!-- Bottom App Navigation -->
    <div class="glass fixed bottom-0 inset-x-0 z-40 border-t border-slate-800 px-6 py-2 flex justify-around items-center text-xs text-slate-400">
        <button onclick="switchTab('scan', this)" class="flex flex-col items-center gap-1 nav-active transition">
            <i class="fa-solid fa-barcode text-lg"></i>
            <span class="font-bold">السكانير</span>
        </button>
        <button onclick="switchTab('products', this)" class="flex flex-col items-center gap-1 transition">
            <i class="fa-solid fa-boxes-stacked text-lg"></i>
            <span class="font-bold">السلعة (<span id="nav-count">0</span>)</span>
        </button>
        <button onclick="switchTab('dash', this)" class="flex flex-col items-center gap-1 transition">
            <i class="fa-solid fa-chart-pie text-lg"></i>
            <span class="font-bold">الأرباح</span>
        </button>
        <button onclick="switchTab('history', this)" class="flex flex-col items-center gap-1 transition">
            <i class="fa-solid fa-clock-rotate-left text-lg"></i>
            <span class="font-bold">السجل</span>
        </button>
    </div>

<script>
    let allProducts = [];
    let currentProduct = null;
    let scanMode = 'info';
    let html5QrCode = null;
    let torchOn = false;
    let lastScanTime = 0;

    // 1. الصوت ديال السكانير (BEEP) بلا ملفات خارجية
    function playBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(1400, ctx.currentTime);
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.12);
            if (navigator.vibrate) navigator.vibrate(100);
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
        ['info', 'out', 'in'].forEach(m => {
            const btn = document.getElementById('mode-' + m);
            btn.className = (m === mode) 
                ? "py-2.5 rounded-xl bg-sky-500 text-slate-950 transition font-extrabold shadow"
                : "py-2.5 rounded-xl text-slate-300 transition";
        });
    }

    // 2. تشغيل الكاميرا بدعم كامل لـ 1D Barcodes
    function startCamera() {
        document.getElementById('scanner-placeholder').classList.add('hidden');
        document.getElementById('reader').classList.remove('hidden');
        document.getElementById('camera-controls').classList.remove('hidden');

        html5QrCode = new Html5Qrcode("reader", {
            experimentalFeatures: { useBarCodeDetectorIfSupported: true }
        });

        const config = {
            fps: 15,
            qrbox: { width: 260, height: 120 },
            aspectRatio: 1.333
        };

        html5QrCode.start(
            { facingMode: "environment" },
            config,
            (decodedText) => {
                const now = Date.now();
                if (now - lastScanTime < 1800) return; // تفادي التكرار السريع
                lastScanTime = now;
                playBeep();
                handleBarcode(decodedText);
            }
        ).catch(err => {
            Swal.fire('تنبيه الكاميرا', 'تأكد أنك عطيتي الصلاحية للكاميرا (Autoriser) أو استعمل زر "صوّر الكود".', 'warning');
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
        html5QrCode.applyVideoConstraints({ advanced: [{ torch: torchOn }] }).catch(() => {
            Swal.fire('الفلاش', 'الفلاش ما مدعومش فهاد المتصفح', 'info');
        });
    }

    function scanFromFile(input) {
        if (input.files.length === 0) return;
        const file = input.files[0];
        const fileScanner = new Html5Qrcode("reader");
        fileScanner.scanFile(file, true)
            .then(decodedText => {
                playBeep();
                handleBarcode(decodedText);
            })
            .catch(() => Swal.fire('ما بانش الكود', 'قرّب الكاميرا شوية للكود-بار باش يبان واضح', 'error'));
    }

    // 3. معالجة الكود-بار على حساب الوضعية
    function handleBarcode(code) {
        code = (code || '').trim();
        if (!code) return;
        document.getElementById('manual-barcode').value = code;

        const found = allProducts.find(p => p.barcode === code);

        if (!found) {
            Swal.fire({
                title: 'سلعة جديدة!',
                text: `الكود (${code}) ما مسجلش عندك. بغيتي تزيدو دابا؟`,
                icon: 'info',
                showCancelButton: true,
                confirmButtonText: 'نعم، سجلها دابا',
                cancelButtonText: 'إلغاء'
            }).then(res => {
                if (res.isConfirmed) openAddModal(code);
            });
            return;
        }

        currentProduct = found;
        showProductCard(found);

        if (scanMode === 'out') {
            updateStockAPI(found.barcode, 1, 'remove');
        } else if (scanMode === 'in') {
            updateStockAPI(found.barcode, 1, 'add');
        }
    }

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
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    toast: true, position: 'top', timer: 1500, showConfirmButton: false,
                    icon: 'success', title: data.message
                });
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

    function closeModal() {
        document.getElementById('product-modal').classList.add('hidden');
    }

    function generateBarcode() {
        const randomCode = '611' + Math.floor(100000000 + Math.random() * 900000000);
        document.getElementById('form-barcode').value = randomCode;
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
        })
        .then(r => r.json())
        .then(() => {
            closeModal();
            playBeep();
            Swal.fire({ toast: true, position: 'top', timer: 1500, showConfirmButton: false, icon: 'success', title: 'تم حفظ السلعة بنجاح!' });
            loadData(payload.barcode);
        });
    }

    function deleteProduct(id) {
        Swal.fire({
            title: 'مسح السلعة؟', text: 'واش متأكد بغيتي تمسح هاد السلعة نهائياً؟', icon: 'warning',
            showCancelButton: true, confirmButtonColor: '#ef4444', confirmButtonText: 'نعم، مسحها', cancelButtonText: 'لا'
        }).then(res => {
            if (res.isConfirmed) {
                fetch('/api/delete/' + id, { method: 'DELETE' }).then(() => loadData());
            }
        });
    }

    function loadData(focusBarcode = null) {
        fetch('/api/data')
            .then(r => r.json())
            .then(data => {
                allProducts = data.products;
                document.getElementById('nav-count').innerText = allProducts.length;
                document.getElementById('stat-items').innerText = data.stats.total_items;
                document.getElementById('stat-capital').innerText = data.stats.total_capital.toFixed(2) + ' DH';
                document.getElementById('stat-profit').innerText = '+' + data.stats.total_profit.toFixed(2) + ' DH';

                renderProducts();
                renderLowStock();
                renderHistory(data.movements);

                if (focusBarcode) {
                    const updated = allProducts.find(p => p.barcode === focusBarcode);
                    if (updated) {
                        currentProduct = updated;
                        showProductCard(updated);
                    }
                }
            });
    }

    function renderProducts() {
        const q = (document.getElementById('search-input').value || '').toLowerCase();
        const container = document.getElementById('products-list');
        const filtered = allProducts.filter(p => 
            p.name.toLowerCase().includes(q) || p.barcode.includes(q) || p.category.toLowerCase().includes(q)
        );

        if (filtered.length === 0) {
            container.innerHTML = `<div class="glass p-6 rounded-2xl text-center text-slate-400 text-xs">ما كاينة حتى سلعة مطابقة.</div>`;
            return;
        }

        container.innerHTML = filtered.map(p => `
            <div onclick="selectFromList('${p.barcode}')" class="glass p-3.5 rounded-2xl flex justify-between items-center cursor-pointer hover:border-sky-500/40 transition">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-[10px] bg-slate-800 text-sky-400 px-2 py-0.5 rounded">${p.category}</span>
                        <code class="text-[11px] text-slate-400">#${p.barcode}</code>
                    </div>
                    <h4 class="font-bold text-sm text-white mt-1">${p.name}</h4>
                    <div class="flex gap-3 mt-1 text-xs">
                        <span class="text-amber-400">شراء: <b>${p.buy_price.toFixed(2)} DH</b></span>
                        <span class="text-emerald-400">بيع: <b>${p.sell_price.toFixed(2)} DH</b></span>
                    </div>
                </div>
                <div class="text-left flex flex-col items-end gap-2">
                    <span class="px-2.5 py-1 rounded-xl font-black text-xs ${p.quantity <= p.min_stock ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' : 'bg-emerald-500/20 text-emerald-400'}">
                        ${p.quantity} فـ الستوك
                    </span>
                    <button onclick="event.stopPropagation(); deleteProduct(${p.id})" class="text-slate-500 hover:text-rose-400 text-xs">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    function selectFromList(barcode) {
        document.querySelectorAll('.fixed.bottom-0 button')[0].click();
        handleBarcode(barcode);
    }

    function renderLowStock() {
        const low = allProducts.filter(p => p.quantity <= p.min_stock);
        const box = document.getElementById('low-stock-list');
        if (low.length === 0) {
            box.innerHTML = `<p class="text-emerald-400">✅ كاع السلعة متوفرة بكمية كافية!</p>`;
            return;
        }
        box.innerHTML = low.map(p => `
            <div class="bg-rose-500/10 border border-rose-500/20 p-2.5 rounded-xl flex justify-between items-center">
                <span><b>${p.name}</b> (#${p.barcode})</span>
                <span class="bg-rose-500 text-white px-2 py-0.5 rounded-lg font-bold">بقات ${p.quantity}</span>
            </div>
        `).join('');
    }

    function renderHistory(moves) {
        const box = document.getElementById('history-list');
        if (!moves || moves.length === 0) {
            box.innerHTML = `<p class="text-slate-400">مازال ما كاين حتى تحرك مسجل.</p>`;
            return;
        }
        box.innerHTML = moves.map(m => `
            <div class="bg-slate-900/80 p-2.5 rounded-xl flex justify-between items-center border border-slate-800">
                <div>
                    <b class="text-white block">${m.product_name}</b>
                    <span class="text-[10px] text-slate-400">${m.created_at}</span>
                </div>
                <span class="font-bold px-2.5 py-1 rounded-lg ${m.move_type === 'IN' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">
                    ${m.move_type === 'IN' ? '+' + m.qty + ' دخلة' : '-' + m.qty + ' خرجة'}
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
    return render_template_string(HTML_PAGE)

@app.route("/api/data")
def get_data():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM products ORDER BY id DESC")
        rows = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM movements ORDER BY id DESC LIMIT 40")
        moves = [dict(r) for r in c.fetchall()]

    total_items = sum(p["quantity"] for p in rows)
    total_capital = sum(p["quantity"] * p["buy_price"] for p in rows)
    total_profit = sum(p["quantity"] * (p["sell_price"] - p["buy_price"]) for p in rows)

    return jsonify({
        "products": rows,
        "movements": moves,
        "stats": {
            "total_items": total_items,
            "total_capital": total_capital,
            "total_profit": total_profit
        }
    })

@app.route("/api/save_product", methods=["POST"])
def save_product():
    init_db()
    d = request.json
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE barcode = ?", (d["barcode"],))
        exists = c.fetchone()
        if exists:
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
        headers={"Content-Disposition": "attachment;filename=stock_warehouse.csv"}
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
