from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
from datetime import datetime
import sqlite3, os

BASE = Path(__file__).resolve().parent
DB = BASE / 'wishbridge.db'
UPLOADS = BASE / 'uploads'
UPLOADS.mkdir(exist_ok=True)
ALLOWED = {'pdf','png','jpg','jpeg'}
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-key-change-before-deployment')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def money(n): return f'₹{float(n or 0):,.2f}'
app.jinja_env.filters['money'] = money

def dbconn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
    with dbconn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('beneficiary','donor','admin')),created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS wishes(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,goal REAL NOT NULL CHECK(goal>0),needed_by TEXT,location TEXT,beneficiary_id INTEGER NOT NULL,document TEXT,status TEXT NOT NULL DEFAULT 'Pending Verification',admin_note TEXT,created_at TEXT NOT NULL,FOREIGN KEY(beneficiary_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS donations(id INTEGER PRIMARY KEY AUTOINCREMENT,wish_id INTEGER NOT NULL,donor_id INTEGER NOT NULL,amount REAL NOT NULL CHECK(amount>0),message TEXT,status TEXT NOT NULL DEFAULT 'Recorded',created_at TEXT NOT NULL,FOREIGN KEY(wish_id) REFERENCES wishes(id),FOREIGN KEY(donor_id) REFERENCES users(id));
        ''')
        if not c.execute('SELECT id FROM users WHERE email=?',('admin@wish.local',)).fetchone():
            c.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',('System Administrator','admin@wish.local',generate_password_hash('Admin123!'),'admin',now()))

def user():
    if not session.get('user_id'): return None
    with dbconn() as c: return c.execute('SELECT id,name,email,role FROM users WHERE id=?',(session['user_id'],)).fetchone()
def login_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if not user(): flash('Please log in first.','error'); return redirect(url_for('login'))
        return fn(*a,**kw)
    return inner
def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        def inner(*a,**kw):
            u=user()
            if not u: return redirect(url_for('login'))
            if u['role'] not in allowed: abort(403)
            return fn(*a,**kw)
        return inner
    return deco
@app.context_processor
def inject(): return {'logged_user':user(),'year':datetime.now().year}

def raised(wid):
    with dbconn() as c: return c.execute("SELECT COALESCE(SUM(amount),0) n FROM donations WHERE wish_id=? AND status='Recorded'",(wid,)).fetchone()['n']
def enrich(rows):
    out=[]
    for r in rows:
        d=dict(r); d['raised']=raised(d['id']); d['progress']=min(100,round(d['raised']/d['goal']*100)) if d['goal'] else 0; out.append(d)
    return out

@app.route('/')
def index():
    with dbconn() as c:
        stats={'verified':c.execute("SELECT COUNT(*) n FROM wishes WHERE status IN ('Verified','Partially Funded')").fetchone()['n'], 'fulfilled':c.execute("SELECT COUNT(*) n FROM wishes WHERE status='Fulfilled'").fetchone()['n'], 'donors':c.execute("SELECT COUNT(*) n FROM users WHERE role='donor'").fetchone()['n']}
        rows=c.execute("SELECT w.*,u.name beneficiary_name FROM wishes w JOIN users u ON u.id=w.beneficiary_id WHERE w.status IN ('Verified','Partially Funded','Fulfilled') ORDER BY w.created_at DESC LIMIT 3").fetchall()
    return render_template('index.html',stats=stats,wishes=enrich(rows))

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); role=request.form.get('role','')
        if not name or not email or len(password)<6 or role not in ('beneficiary','donor'):
            flash('Enter all details and use a password of at least 6 characters.','error')
        else:
            try:
                with dbconn() as c: cur=c.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(password),role,now()))
                session.clear(); session['user_id']=cur.lastrowid; flash('Account created successfully.','success'); return redirect(url_for('dashboard'))
            except sqlite3.IntegrityError: flash('That email is already registered.','error')
    return render_template('register.html')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        with dbconn() as c: u=c.execute('SELECT * FROM users WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
        if u and check_password_hash(u['password_hash'],request.form.get('password','')):
            session.clear(); session['user_id']=u['id']; return redirect(url_for('dashboard'))
        flash('Email or password is incorrect.','error')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))
@app.route('/dashboard')
@login_required
def dashboard():
    u=user()
    with dbconn() as c:
        if u['role']=='admin':
            rows=c.execute('SELECT w.*,u.name beneficiary_name FROM wishes w JOIN users u ON u.id=w.beneficiary_id ORDER BY w.created_at DESC').fetchall()
            counts={'pending':c.execute("SELECT COUNT(*) n FROM wishes WHERE status='Pending Verification'").fetchone()['n'],'verified':c.execute("SELECT COUNT(*) n FROM wishes WHERE status IN ('Verified','Partially Funded')").fetchone()['n'],'fulfilled':c.execute("SELECT COUNT(*) n FROM wishes WHERE status='Fulfilled'").fetchone()['n'],'donations':c.execute("SELECT COALESCE(SUM(amount),0) n FROM donations WHERE status='Recorded'").fetchone()['n']}
            return render_template('dashboard_admin.html',wishes=enrich(rows),counts=counts)
        if u['role']=='beneficiary':
            rows=c.execute('SELECT * FROM wishes WHERE beneficiary_id=? ORDER BY created_at DESC',(u['id'],)).fetchall()
            return render_template('dashboard_beneficiary.html',wishes=enrich(rows))
        donations=c.execute('SELECT d.*,w.title,w.status wish_status FROM donations d JOIN wishes w ON w.id=d.wish_id WHERE d.donor_id=? ORDER BY d.created_at DESC',(u['id'],)).fetchall()
        return render_template('dashboard_donor.html',donations=donations)
@app.route('/wishes')
def wishes():
    category=request.args.get('category','').strip(); q=request.args.get('q','').strip()
    sql="SELECT w.*,u.name beneficiary_name FROM wishes w JOIN users u ON u.id=w.beneficiary_id WHERE w.status IN ('Verified','Partially Funded')"; args=[]
    if category: sql+=' AND w.category=?'; args.append(category)
    if q: sql+=' AND (w.title LIKE ? OR w.description LIKE ? OR w.location LIKE ?)'; args += [f'%{q}%']*3
    sql+=' ORDER BY w.needed_by IS NULL,w.needed_by ASC,w.created_at DESC'
    with dbconn() as c:
        rows=c.execute(sql,args).fetchall(); cats=[r['category'] for r in c.execute("SELECT DISTINCT category FROM wishes WHERE status IN ('Verified','Partially Funded') ORDER BY category").fetchall()]
    return render_template('wishes.html',wishes=enrich(rows),categories=cats,selected=category,q=q)
@app.route('/wish/new',methods=['GET','POST'])
@login_required
@roles('beneficiary')
def new_wish():
    if request.method=='POST':
        title=request.form.get('title','').strip(); category=request.form.get('category','').strip(); desc=request.form.get('description','').strip(); location=request.form.get('location','').strip(); needed=request.form.get('needed_by','').strip()
        try: goal=float(request.form.get('goal','0'))
        except ValueError: goal=0
        file=request.files.get('document'); filename=None
        if file and file.filename:
            safe=secure_filename(file.filename); ext=safe.rsplit('.',1)[-1].lower() if '.' in safe else ''
            if ext not in ALLOWED: flash('Supporting document must be PDF, PNG, JPG or JPEG.','error'); return render_template('new_wish.html')
            filename=f'{datetime.now().strftime("%Y%m%d%H%M%S%f")}_{safe}'; file.save(UPLOADS/filename)
        if not title or not category or not desc or goal<=0:
            flash('Complete required fields and enter a goal amount greater than zero.','error'); return render_template('new_wish.html')
        with dbconn() as c: c.execute('INSERT INTO wishes(title,category,description,goal,needed_by,location,beneficiary_id,document,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(title,category,desc,goal,needed or None,location,user()['id'],filename,'Pending Verification',now()))
        flash('Your request has been submitted for verification. It will not appear publicly until approved.','success'); return redirect(url_for('dashboard'))
    return render_template('new_wish.html')
@app.route('/wish/<int:wish_id>')
def wish_detail(wish_id):
    with dbconn() as c:
        row=c.execute('SELECT w.*,u.name beneficiary_name FROM wishes w JOIN users u ON u.id=w.beneficiary_id WHERE w.id=?',(wish_id,)).fetchone()
        if not row: abort(404)
        u=user()
        if row['status']=='Pending Verification' and (not u or (u['role']!='admin' and u['id']!=row['beneficiary_id'])): abort(404)
        donations=c.execute("SELECT d.amount,d.message,d.created_at,u.name donor_name FROM donations d JOIN users u ON u.id=d.donor_id WHERE d.wish_id=? AND d.status='Recorded' ORDER BY d.created_at DESC",(wish_id,)).fetchall()
    w=enrich([row])[0]; return render_template('wish_detail.html',wish=w,donations=donations)
@app.route('/wish/<int:wish_id>/donate',methods=['POST'])
@login_required
@roles('donor')
def donate(wish_id):
    try: amount=round(float(request.form.get('amount','0')),2)
    except ValueError: amount=0
    message=request.form.get('message','').strip()
    with dbconn() as c: w=c.execute("SELECT * FROM wishes WHERE id=? AND status IN ('Verified','Partially Funded')",(wish_id,)).fetchone()
    if not w: flash('This request is not accepting contributions.','error'); return redirect(url_for('wishes'))
    remaining=max(0,w['goal']-raised(wish_id))
    if amount<=0 or amount>remaining: flash(f'Enter an amount above ₹0 and no more than the remaining goal ({money(remaining)}).','error'); return redirect(url_for('wish_detail',wish_id=wish_id))
    with dbconn() as c: c.execute('INSERT INTO donations(wish_id,donor_id,amount,message,status,created_at) VALUES(?,?,?,?,?,?)',(wish_id,user()['id'],amount,message,'Recorded',now()))
    total=raised(wish_id)
    with dbconn() as c: c.execute('UPDATE wishes SET status=? WHERE id=?',('Fulfilled' if total>=w['goal'] else 'Partially Funded' if total>0 else 'Verified',wish_id))
    flash('Contribution recorded in this demo. No real money was transferred.','success'); return redirect(url_for('wish_detail',wish_id=wish_id))
@app.route('/admin/wish/<int:wish_id>/review',methods=['POST'])
@login_required
@roles('admin')
def review(wish_id):
    action=request.form.get('action'); note=request.form.get('admin_note','').strip()
    if action not in ('approve','reject'): abort(400)
    with dbconn() as c:
        w=c.execute('SELECT id,status FROM wishes WHERE id=?',(wish_id,)).fetchone()
        if not w: abort(404)
        c.execute('UPDATE wishes SET status=?,admin_note=? WHERE id=?',('Verified' if action=='approve' else 'Rejected',note,wish_id))
    flash('Request verified and published.' if action=='approve' else 'Request rejected.','success'); return redirect(url_for('dashboard'))
@app.route('/uploads/<path:filename>')
@login_required
@roles('admin')
def upload(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOADS,filename,as_attachment=True)
@app.errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='You do not have permission to view this page.'),403
@app.errorhandler(404)
def missing(e): return render_template('error.html',code=404,message='This page or request could not be found.'),404
init_db()
if __name__=='__main__': app.run(debug=True)
