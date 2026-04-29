"""
BuildSmart — Backend Flask Complet v2
Gestion de la Conception Architecturale
"""

from flask import Flask, request, jsonify, session, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
import os, json, uuid

app = Flask(__name__)
app.secret_key = 'buildsmart_ultra_secret_2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///buildsmart.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# Track online users: {user_id: socket_sid}
online_users = {}

# ═══════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Non authentifié', 'code': 401}), 401
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Non authentifié'}), 401
            user = Utilisateur.query.get(session['user_id'])
            if not user or user.role not in roles:
                return jsonify({'error': f'Accès refusé. Rôle requis: {list(roles)}'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def get_current_user():
    if 'user_id' in session:
        return Utilisateur.query.get(session['user_id'])
    return None

def gen_reference(prefix, model):
    year = datetime.utcnow().year
    count = model.query.count() + 1
    return f"{prefix}-{year}-{count:04d}"

def create_notification(user_id, titre, contenu, type_notif='info'):
    notif = Notification(user_id=user_id, titre=titre, contenu=contenu, type_notif=type_notif)
    db.session.add(notif)

def save_file(file_obj, prefix='file'):
    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    fname = f"{prefix}_{uuid.uuid4().hex}.{ext}"
    file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
    return f"/static/uploads/{fname}"


# ═══════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════

class Utilisateur(db.Model):
    __tablename__ = 'utilisateurs'
    id                  = db.Column(db.Integer, primary_key=True)
    nom                 = db.Column(db.String(100), nullable=False)
    prenom              = db.Column(db.String(100), nullable=False)
    email               = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe        = db.Column(db.String(200), nullable=False)
    role                = db.Column(db.String(20), nullable=False)
    avatar              = db.Column(db.String(200), default=None)
    telephone           = db.Column(db.String(20), default='')
    ville               = db.Column(db.String(100), default='')
    bio                 = db.Column(db.Text, default='')
    specialites         = db.Column(db.Text, default='[]')
    experience_ans      = db.Column(db.Integer, default=0)
    note_moyenne        = db.Column(db.Float, default=0.0)
    nb_projets_termines = db.Column(db.Integer, default=0)
    tarif_horaire       = db.Column(db.Float, default=0.0)
    disponible          = db.Column(db.Boolean, default=True)
    actif               = db.Column(db.Boolean, default=True)
    date_creation       = db.Column(db.DateTime, default=datetime.utcnow)
    derniere_connexion  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, full=False):
        d = {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'nom_complet': f"{self.prenom} {self.nom}",
            'email': self.email,
            'role': self.role,
            'avatar': self.avatar,
            'telephone': self.telephone,
            'ville': self.ville,
            'date_creation': self.date_creation.strftime('%Y-%m-%d'),
            'initiales': (self.prenom[0] + self.nom[0]).upper() if self.prenom and self.nom else '?',
        }
        if full:
            d.update({
                'bio': self.bio,
                'specialites': json.loads(self.specialites or '[]'),
                'experience_ans': self.experience_ans,
                'note_moyenne': self.note_moyenne,
                'nb_projets_termines': self.nb_projets_termines,
                'tarif_horaire': self.tarif_horaire,
                'disponible': self.disponible,
            })
        return d


class StyleArchitectural(db.Model):
    __tablename__ = 'styles'
    id          = db.Column(db.Integer, primary_key=True)
    nom         = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    emoji       = db.Column(db.String(10), default='🏠')
    couleur_bg  = db.Column(db.String(200), default='linear-gradient(135deg,#1a2570,#2563eb)')
    badge       = db.Column(db.String(50), default='')
    actif       = db.Column(db.Boolean, default=True)
    conceptions = db.relationship('Conception', backref='style_obj', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'description': self.description,
            'emoji': self.emoji,
            'couleur_bg': self.couleur_bg,
            'badge': self.badge,
            'nb_conceptions': len([c for c in self.conceptions if c.statut == 'publie']),
        }


class Conception(db.Model):
    __tablename__ = 'conceptions'
    id               = db.Column(db.Integer, primary_key=True)
    titre            = db.Column(db.String(150), nullable=False)
    description      = db.Column(db.Text)
    style_id         = db.Column(db.Integer, db.ForeignKey('styles.id'))
    statut           = db.Column(db.String(50), default='brouillon')
    prix_base        = db.Column(db.Float, default=0)
    superficie_min   = db.Column(db.Integer, default=0)
    superficie_max   = db.Column(db.Integer, default=0)
    nb_chambres      = db.Column(db.Integer, default=0)
    nb_etages        = db.Column(db.Integer, default=1)
    caracteristiques = db.Column(db.Text, default='[]')
    images           = db.Column(db.Text, default='[]')
    ingenieur_id     = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    ingenieur        = db.relationship('Utilisateur', backref='conceptions')
    nb_vues          = db.Column(db.Integer, default=0)
    nb_likes         = db.Column(db.Integer, default=0)
    date_creation    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'titre': self.titre,
            'description': self.description,
            'style': self.style_obj.nom if self.style_obj else '',
            'style_id': self.style_id,
            'style_emoji': self.style_obj.emoji if self.style_obj else '🏠',
            'style_couleur': self.style_obj.couleur_bg if self.style_obj else '',
            'statut': self.statut,
            'prix_base': self.prix_base,
            'superficie_min': self.superficie_min,
            'superficie_max': self.superficie_max,
            'nb_chambres': self.nb_chambres,
            'nb_etages': self.nb_etages,
            'caracteristiques': json.loads(self.caracteristiques or '[]'),
            'images': json.loads(self.images or '[]'),
            'nb_vues': self.nb_vues,
            'nb_likes': self.nb_likes,
            'ingenieur': self.ingenieur.to_dict(full=True) if self.ingenieur else None,
            'date_creation': self.date_creation.strftime('%Y-%m-%d'),
        }


class Projet(db.Model):
    __tablename__ = 'projets'
    id              = db.Column(db.Integer, primary_key=True)
    reference       = db.Column(db.String(20), unique=True)
    titre           = db.Column(db.String(150), nullable=False)
    description     = db.Column(db.Text, default='')
    adresse         = db.Column(db.String(200), default='')
    ville           = db.Column(db.String(100), default='')
    superficie      = db.Column(db.Float, default=0)
    budget_estime   = db.Column(db.Float, default=0)
    statut          = db.Column(db.String(50), default='en_attente')
    progression     = db.Column(db.Integer, default=0)
    priorite        = db.Column(db.String(20), default='normale')
    notes_client    = db.Column(db.Text, default='')
    date_debut      = db.Column(db.DateTime, default=datetime.utcnow)
    date_fin_prevue = db.Column(db.DateTime)
    date_cloture    = db.Column(db.DateTime)
    client_id       = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    ingenieur_id    = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    conception_id   = db.Column(db.Integer, db.ForeignKey('conceptions.id'))
    client          = db.relationship('Utilisateur', foreign_keys=[client_id], backref='projets_client')
    ingenieur       = db.relationship('Utilisateur', foreign_keys=[ingenieur_id], backref='projets_ingenieur')
    conception      = db.relationship('Conception', backref='projets')

    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'titre': self.titre,
            'description': self.description,
            'adresse': self.adresse,
            'ville': self.ville,
            'superficie': self.superficie,
            'budget_estime': self.budget_estime,
            'statut': self.statut,
            'progression': self.progression,
            'priorite': self.priorite,
            'notes_client': self.notes_client,
            'date_debut': self.date_debut.strftime('%Y-%m-%d'),
            'date_fin_prevue': self.date_fin_prevue.strftime('%Y-%m-%d') if self.date_fin_prevue else None,
            'date_cloture': self.date_cloture.strftime('%Y-%m-%d') if self.date_cloture else None,
            'client': self.client.to_dict() if self.client else None,
            'ingenieur': self.ingenieur.to_dict(full=True) if self.ingenieur else None,
            'conception': self.conception.to_dict() if self.conception else None,
            'paiements': [p.to_dict() for p in self.paiements],
            'nb_messages': len(self.messages),
            'nb_revisions': len(self.revisions),
        }


class Contrat(db.Model):
    __tablename__ = 'contrats'
    id              = db.Column(db.Integer, primary_key=True)
    numero          = db.Column(db.String(30), unique=True)
    projet_id       = db.Column(db.Integer, db.ForeignKey('projets.id'), unique=True)
    montant_total   = db.Column(db.Float)
    montant_initial = db.Column(db.Float)
    montant_final   = db.Column(db.Float)
    conditions      = db.Column(db.Text, default='')
    statut          = db.Column(db.String(50), default='en_attente')
    date_creation   = db.Column(db.DateTime, default=datetime.utcnow)
    date_signature  = db.Column(db.DateTime)
    date_expiration = db.Column(db.DateTime)
    projet          = db.relationship('Projet', backref=db.backref('contrat', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'montant_total': self.montant_total,
            'montant_initial': self.montant_initial,
            'montant_final': self.montant_final,
            'statut': self.statut,
            'conditions': self.conditions,
            'date_creation': self.date_creation.strftime('%Y-%m-%d'),
            'date_signature': self.date_signature.strftime('%Y-%m-%d') if self.date_signature else None,
            'date_expiration': self.date_expiration.strftime('%Y-%m-%d') if self.date_expiration else None,
        }


class Paiement(db.Model):
    __tablename__ = 'paiements'
    id            = db.Column(db.Integer, primary_key=True)
    reference     = db.Column(db.String(30), unique=True)
    projet_id     = db.Column(db.Integer, db.ForeignKey('projets.id'))
    montant       = db.Column(db.Float)
    type_paiement = db.Column(db.String(50))
    methode       = db.Column(db.String(50), default='carte')
    statut        = db.Column(db.String(50), default='en_attente')
    notes         = db.Column(db.String(200), default='')
    date_paiement = db.Column(db.DateTime)
    projet        = db.relationship('Projet', backref='paiements')

    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'montant': self.montant,
            'type': self.type_paiement,
            'methode': self.methode,
            'statut': self.statut,
            'notes': self.notes,
            'date': self.date_paiement.strftime('%Y-%m-%d %H:%M') if self.date_paiement else None,
        }


class Message(db.Model):
    __tablename__ = 'messages'
    id            = db.Column(db.Integer, primary_key=True)
    projet_id     = db.Column(db.Integer, db.ForeignKey('projets.id'))
    expediteur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    contenu       = db.Column(db.Text, nullable=False)
    type_msg      = db.Column(db.String(20), default='texte')
    fichier_url   = db.Column(db.String(200), default='')
    lu            = db.Column(db.Boolean, default=False)
    date_envoi    = db.Column(db.DateTime, default=datetime.utcnow)
    expediteur    = db.relationship('Utilisateur', backref='messages')
    projet        = db.relationship('Projet', backref='messages')

    def to_dict(self):
        return {
            'id': self.id,
            'contenu': self.contenu,
            'type': self.type_msg,
            'fichier_url': self.fichier_url,
            'lu': self.lu,
            'expediteur_id': self.expediteur_id,
            'expediteur_nom': self.expediteur.to_dict()['nom_complet'] if self.expediteur else '?',
            'expediteur_avatar': self.expediteur.avatar if self.expediteur else None,
            'expediteur_role': self.expediteur.role if self.expediteur else '',
            'expediteur_initiales': self.expediteur.to_dict()['initiales'] if self.expediteur else '?',
            'date': self.date_envoi.strftime('%H:%M'),
            'date_complete': self.date_envoi.strftime('%d/%m/%Y %H:%M'),
        }


class MessageDirect(db.Model):
    """Direct messages between any two users (independent of projects)."""
    __tablename__ = 'messages_directs'
    id              = db.Column(db.Integer, primary_key=True)
    expediteur_id   = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    destinataire_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    contenu         = db.Column(db.Text, nullable=False)
    lu              = db.Column(db.Boolean, default=False)
    date_envoi      = db.Column(db.DateTime, default=datetime.utcnow)
    expediteur      = db.relationship('Utilisateur', foreign_keys=[expediteur_id], backref='dm_envoyes')
    destinataire    = db.relationship('Utilisateur', foreign_keys=[destinataire_id], backref='dm_recus')

    def to_dict(self):
        exp = self.expediteur
        return {
            'id': self.id,
            'expediteur_id': self.expediteur_id,
            'destinataire_id': self.destinataire_id,
            'contenu': self.contenu,
            'lu': self.lu,
            'date': self.date_envoi.strftime('%H:%M'),
            'date_complete': self.date_envoi.strftime('%d/%m/%Y %H:%M'),
            'expediteur_nom': f"{exp.prenom} {exp.nom}" if exp else '?',
            'expediteur_initiales': (exp.prenom[0]+exp.nom[0]).upper() if exp else '?',
            'expediteur_avatar': exp.avatar if exp else None,
            'expediteur_role': exp.role if exp else '',
        }


class Revision(db.Model):
    __tablename__ = 'revisions'
    id              = db.Column(db.Integer, primary_key=True)
    projet_id       = db.Column(db.Integer, db.ForeignKey('projets.id'))
    demandeur_id    = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    description     = db.Column(db.Text, nullable=False)
    statut          = db.Column(db.String(30), default='en_attente')
    priorite        = db.Column(db.String(20), default='normale')
    date_demande    = db.Column(db.DateTime, default=datetime.utcnow)
    date_traitement = db.Column(db.DateTime)
    projet          = db.relationship('Projet', backref='revisions')
    demandeur       = db.relationship('Utilisateur', backref='revisions')

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'statut': self.statut,
            'priorite': self.priorite,
            'demandeur': self.demandeur.to_dict()['nom_complet'] if self.demandeur else '?',
            'date': self.date_demande.strftime('%d/%m/%Y'),
            'date_traitement': self.date_traitement.strftime('%d/%m/%Y') if self.date_traitement else None,
        }


class Notification(db.Model):
    __tablename__ = 'notifications'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    titre         = db.Column(db.String(150))
    contenu       = db.Column(db.Text)
    type_notif    = db.Column(db.String(50), default='info')
    lue           = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    user          = db.relationship('Utilisateur', backref='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'titre': self.titre,
            'contenu': self.contenu,
            'type': self.type_notif,
            'lue': self.lue,
            'date': self.date_creation.strftime('%d/%m/%Y %H:%M'),
        }


class Avis(db.Model):
    __tablename__ = 'avis'
    id           = db.Column(db.Integer, primary_key=True)
    projet_id    = db.Column(db.Integer, db.ForeignKey('projets.id'))
    client_id    = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    ingenieur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    note         = db.Column(db.Integer)
    commentaire  = db.Column(db.Text)
    date_avis    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        client = Utilisateur.query.get(self.client_id)
        return {
            'id': self.id,
            'note': self.note,
            'commentaire': self.commentaire,
            'client': client.to_dict()['nom_complet'] if client else '?',
            'client_avatar': client.avatar if client else None,
            'date': self.date_avis.strftime('%d/%m/%Y'),
        }


# ═══════════════════════════════════════
#  ROUTES PAGES
# ═══════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ═══════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════
@app.route('/api/auth/register', methods=['POST'])
def register():
    is_multipart = request.content_type and 'multipart' in request.content_type
    data = request.form if is_multipart else (request.json or {})

    required = ['nom', 'prenom', 'email', 'mot_de_passe', 'role']
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({'error': f'Champs manquants: {missing}'}), 400
    if data['role'] not in ['client', 'ingenieur']:
        return jsonify({'error': 'Rôle invalide (client ou ingenieur)'}), 400
    if Utilisateur.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email déjà utilisé'}), 409

    avatar_path = None
    if 'avatar' in request.files:
        f = request.files['avatar']
        if f and allowed_file(f.filename):
            avatar_path = save_file(f, 'avatar')

    specs = data.get('specialites', '')
    if isinstance(specs, str):
        specs = [s.strip() for s in specs.split(',') if s.strip()]

    user = Utilisateur(
        nom=data['nom'], prenom=data['prenom'], email=data['email'],
        mot_de_passe=generate_password_hash(data['mot_de_passe']),
        role=data['role'], avatar=avatar_path,
        telephone=data.get('telephone', ''), ville=data.get('ville', ''),
        bio=data.get('bio', ''), specialites=json.dumps(specs),
        experience_ans=int(data.get('experience_ans', 0) or 0),
        tarif_horaire=float(data.get('tarif_horaire', 0) or 0),
    )
    db.session.add(user)
    db.session.flush()
    create_notification(user.id, 'Bienvenue sur BuildSmart! 🎉',
                        f'Bonjour {user.prenom}, votre compte est prêt.', 'succes')
    db.session.commit()
    session['user_id'] = user.id
    session['role'] = user.role
    return jsonify({'message': 'Compte créé', 'user': user.to_dict(full=True)}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json if request.is_json else request.form
    print(data)

    user = Utilisateur.query.filter_by(email=data.get('email', '')).first()

    password = data.get('mot_de_passe') or data.get('password')

    if not user or not check_password_hash(user.mot_de_passe, password):
        return jsonify({'error': 'Email ou mot de passe incorrect'}), 401

    if not user.actif:
        return jsonify({'error': 'Compte désactivé'}), 403

    user.derniere_connexion = datetime.utcnow()
    db.session.commit()

    session['user_id'] = user.id
    session['role'] = user.role

    return jsonify({'message': 'Connexion réussie', 'user': user.to_dict(full=True)})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Déconnecté'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def me():
    return jsonify(get_current_user().to_dict(full=True))


@app.route('/api/auth/me', methods=['PUT'])
@login_required
def update_profile():
    user = get_current_user()
    is_mp = request.content_type and 'multipart' in request.content_type
    data = request.form if is_mp else (request.json or {})

    if 'avatar' in request.files:
        f = request.files['avatar']
        if f and allowed_file(f.filename):
            if user.avatar:
                old = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(user.avatar))
                if os.path.exists(old): os.remove(old)
            user.avatar = save_file(f, 'avatar')

    for field in ['nom', 'prenom', 'telephone', 'ville', 'bio']:
        if field in data and data[field]:
            setattr(user, field, data[field])

    if user.role == 'ingenieur':
        if 'specialites' in data:
            s = data['specialites']
            user.specialites = json.dumps(s if isinstance(s, list) else [x.strip() for x in s.split(',') if x.strip()])
        if 'experience_ans' in data:
            user.experience_ans = int(data['experience_ans'] or 0)
        if 'tarif_horaire' in data:
            user.tarif_horaire = float(data['tarif_horaire'] or 0)
        if 'disponible' in data:
            user.disponible = str(data['disponible']).lower() in ('true', '1', 'oui')

    if data.get('mot_de_passe'):
        user.mot_de_passe = generate_password_hash(data['mot_de_passe'])

    db.session.commit()
    return jsonify({'message': 'Profil mis à jour', 'user': user.to_dict(full=True)})


# ═══════════════════════════════════════
#  STYLES
# ═══════════════════════════════════════
@app.route('/api/styles', methods=['GET'])
def get_styles():
    styles = StyleArchitectural.query.filter_by(actif=True).all()
    return jsonify([s.to_dict() for s in styles])


# ═══════════════════════════════════════
#  CONCEPTIONS
# ═══════════════════════════════════════
@app.route('/api/conceptions', methods=['GET'])
def get_conceptions():
    style_id  = request.args.get('style_id', type=int)
    style_nom = request.args.get('style')
    statut    = request.args.get('statut', 'publie')
    min_prix  = request.args.get('min_prix', type=float)
    max_prix  = request.args.get('max_prix', type=float)
    chambres  = request.args.get('chambres', type=int)
    search    = request.args.get('q', '')
    sort      = request.args.get('sort', 'date')
    page      = request.args.get('page', 1, type=int)
    per_page  = request.args.get('per_page', 12, type=int)

    q = Conception.query
    if statut:    q = q.filter_by(statut=statut)
    if style_id:  q = q.filter_by(style_id=style_id)
    if style_nom:
        s = StyleArchitectural.query.filter_by(nom=style_nom).first()
        if s: q = q.filter_by(style_id=s.id)
    if min_prix:  q = q.filter(Conception.prix_base >= min_prix)
    if max_prix:  q = q.filter(Conception.prix_base <= max_prix)
    if chambres:  q = q.filter(Conception.nb_chambres >= chambres)
    if search:    q = q.filter(db.or_(Conception.titre.ilike(f'%{search}%'),
                                       Conception.description.ilike(f'%{search}%')))
    if sort == 'prix':   q = q.order_by(Conception.prix_base)
    elif sort == 'vues': q = q.order_by(Conception.nb_vues.desc())
    elif sort == 'likes':q = q.order_by(Conception.nb_likes.desc())
    else:                q = q.order_by(Conception.date_creation.desc())

    total = q.count()
    items = q.offset((page-1)*per_page).limit(per_page).all()
    return jsonify({
        'total': total, 'page': page, 'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'items': [c.to_dict() for c in items]
    })


@app.route('/api/conceptions/<int:cid>', methods=['GET'])
def get_conception(cid):
    c = Conception.query.get_or_404(cid)
    c.nb_vues += 1
    db.session.commit()
    d = c.to_dict()
    if c.ingenieur:
        avis = Avis.query.filter_by(ingenieur_id=c.ingenieur_id).order_by(Avis.date_avis.desc()).limit(5).all()
        d['avis_ingenieur'] = [a.to_dict() for a in avis]
    return jsonify(d)


@app.route('/api/conceptions', methods=['POST'])
@role_required('ingenieur', 'admin')
def create_conception():
    user = get_current_user()
    is_mp = request.content_type and 'multipart' in request.content_type
    data = request.form if is_mp else (request.json or {})

    if not data.get('titre'):
        return jsonify({'error': 'Titre requis'}), 400

    images = []
    if 'images' in request.files:
        for f in request.files.getlist('images'):
            if f and allowed_file(f.filename):
                images.append(save_file(f, 'conc'))

    carac = data.get('caracteristiques', '[]')
    if isinstance(carac, str):
        try:    carac = json.loads(carac)
        except: carac = [x.strip() for x in carac.split(',') if x.strip()]

    c = Conception(
        titre=data['titre'], description=data.get('description', ''),
        style_id=int(data.get('style_id', 1)),
        statut=data.get('statut', 'brouillon'),
        prix_base=float(data.get('prix_base', 0) or 0),
        superficie_min=int(data.get('superficie_min', 0) or 0),
        superficie_max=int(data.get('superficie_max', 0) or 0),
        nb_chambres=int(data.get('nb_chambres', 0) or 0),
        nb_etages=int(data.get('nb_etages', 1) or 1),
        caracteristiques=json.dumps(carac),
        images=json.dumps(images),
        ingenieur_id=user.id,
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({'message': 'Conception créée', 'id': c.id, 'conception': c.to_dict()}), 201


@app.route('/api/conceptions/<int:cid>', methods=['PUT'])
@login_required
def update_conception(cid):
    user = get_current_user()
    c = Conception.query.get_or_404(cid)
    if c.ingenieur_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Accès refusé'}), 403
    is_mp = request.content_type and 'multipart' in request.content_type
    data = request.form if is_mp else (request.json or {})

    if 'images' in request.files:
        existing = json.loads(c.images or '[]')
        for f in request.files.getlist('images'):
            if f and allowed_file(f.filename):
                existing.append(save_file(f, 'conc'))
        c.images = json.dumps(existing)

    for field in ['titre','description','statut','prix_base','superficie_min','superficie_max','nb_chambres','nb_etages']:
        if field in data: setattr(c, field, data[field])
    if 'style_id' in data: c.style_id = int(data['style_id'])
    if 'caracteristiques' in data:
        carac = data['caracteristiques']
        if isinstance(carac, str):
            try: carac = json.loads(carac)
            except: carac = [x.strip() for x in carac.split(',') if x.strip()]
        c.caracteristiques = json.dumps(carac)

    db.session.commit()
    return jsonify({'message': 'Conception mise à jour', 'conception': c.to_dict()})


@app.route('/api/conceptions/<int:cid>/like', methods=['POST'])
@login_required
def like_conception(cid):
    c = Conception.query.get_or_404(cid)
    c.nb_likes += 1
    db.session.commit()
    return jsonify({'nb_likes': c.nb_likes})


# ═══════════════════════════════════════
#  INGÉNIEURS
# ═══════════════════════════════════════
@app.route('/api/ingenieurs', methods=['GET'])
def get_ingenieurs():
    ville    = request.args.get('ville')
    dispo    = request.args.get('disponible')
    min_note = request.args.get('min_note', type=float)
    sort     = request.args.get('sort', 'note')

    q = Utilisateur.query.filter_by(role='ingenieur', actif=True)
    if ville:    q = q.filter(Utilisateur.ville.ilike(f'%{ville}%'))
    if dispo=='1': q = q.filter_by(disponible=True)
    if min_note: q = q.filter(Utilisateur.note_moyenne >= min_note)
    if sort=='note':    q = q.order_by(Utilisateur.note_moyenne.desc())
    elif sort=='projets': q = q.order_by(Utilisateur.nb_projets_termines.desc())

    return jsonify([u.to_dict(full=True) for u in q.all()])


@app.route('/api/ingenieurs/<int:uid>', methods=['GET'])
def get_ingenieur(uid):
    ing = Utilisateur.query.filter_by(id=uid, role='ingenieur').first_or_404()
    d = ing.to_dict(full=True)
    d['conceptions'] = [c.to_dict() for c in ing.conceptions if c.statut == 'publie']
    d['avis'] = [a.to_dict() for a in Avis.query.filter_by(ingenieur_id=uid).order_by(Avis.date_avis.desc()).limit(10).all()]
    return jsonify(d)


# ═══════════════════════════════════════
#  PROJETS
# ═══════════════════════════════════════
@app.route('/api/projets', methods=['GET'])
@login_required
def get_projets():
    user = get_current_user()
    statut = request.args.get('statut')
    if user.role == 'client':   q = Projet.query.filter_by(client_id=user.id)
    elif user.role == 'ingenieur': q = Projet.query.filter_by(ingenieur_id=user.id)
    else:                       q = Projet.query
    if statut: q = q.filter_by(statut=statut)
    return jsonify([p.to_dict() for p in q.order_by(Projet.date_debut.desc()).all()])


@app.route('/api/projets', methods=['POST'])
@role_required('client')
def create_projet():
    user = get_current_user()
    data = request.json or {}
    required = ['titre', 'ingenieur_id', 'conception_id']
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({'error': f'Champs manquants: {missing}'}), 400

    ing = Utilisateur.query.filter_by(id=data['ingenieur_id'], role='ingenieur').first()
    if not ing: return jsonify({'error': 'Ingénieur introuvable'}), 404
    conc = Conception.query.get(data['conception_id'])
    if not conc: return jsonify({'error': 'Conception introuvable'}), 404

    date_fin = None
    if data.get('date_fin_prevue'):
        try: date_fin = datetime.strptime(data['date_fin_prevue'], '%Y-%m-%d')
        except: pass

    p = Projet(
        reference=gen_reference('PRJ', Projet),
        titre=data['titre'], description=data.get('description', ''),
        adresse=data.get('adresse', ''), ville=data.get('ville', ''),
        superficie=float(data.get('superficie', 0) or 0),
        budget_estime=float(data.get('budget_estime', conc.prix_base) or conc.prix_base),
        priorite=data.get('priorite', 'normale'),
        notes_client=data.get('notes_client', ''),
        client_id=user.id, ingenieur_id=data['ingenieur_id'],
        conception_id=data['conception_id'], date_fin_prevue=date_fin,
    )
    db.session.add(p)
    db.session.flush()

    montant = p.budget_estime + 350
    c = Contrat(
        numero=gen_reference('CTR', Contrat), projet_id=p.id,
        montant_total=montant, montant_initial=round(montant*0.5, 2),
        montant_final=round(montant*0.5, 2),
        conditions=f"Contrat de conception pour '{p.titre}'. Paiement en 2 tranches (50%/50%). Révisions incluses.",
        date_expiration=datetime.utcnow() + timedelta(days=30),
    )
    db.session.add(c)

    db.session.add(Message(projet_id=p.id, expediteur_id=user.id,
                           contenu=f"🚀 Projet '{p.titre}' créé. Référence: {p.reference}", type_msg='systeme'))

    create_notification(user.id, '🏛️ Projet créé!',
                        f"'{p.titre}' (ref: {p.reference}) créé avec succès.", 'succes')
    create_notification(ing.id, '📋 Nouvelle demande!',
                        f"{user.prenom} {user.nom} vous a envoyé une demande pour '{p.titre}'.", 'info')
    db.session.commit()
    return jsonify({'message': 'Projet créé', 'projet': p.to_dict()}), 201


@app.route('/api/projets/<int:pid>', methods=['GET'])
@login_required
def get_projet(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if user.role not in ('admin',) and p.client_id != user.id and p.ingenieur_id != user.id:
        return jsonify({'error': 'Accès refusé'}), 403
    return jsonify(p.to_dict())


@app.route('/api/projets/<int:pid>', methods=['PUT'])
@login_required
def update_projet(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.ingenieur_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Accès refusé'}), 403
    data = request.json or {}
    for field in ['titre','description','statut','progression','adresse','ville','priorite']:
        if field in data: setattr(p, field, data[field])
    if 'progression' in data:
        create_notification(p.client_id, f'📊 Progression: {data["progression"]}%',
                            f"Projet '{p.titre}' à {data['progression']}%.", 'info')
    db.session.commit()
    return jsonify({'message': 'Projet mis à jour', 'projet': p.to_dict()})


@app.route('/api/projets/<int:pid>/valider', methods=['POST'])
@role_required('client')
def valider_projet(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.client_id != user.id: return jsonify({'error': 'Accès refusé'}), 403
    p.statut = 'valide'; p.progression = 100
    create_notification(p.ingenieur_id, '✅ Projet validé!', f"Client a validé '{p.titre}'.", 'succes')
    db.session.commit()
    return jsonify({'message': 'Projet validé', 'projet': p.to_dict()})


@app.route('/api/projets/<int:pid>/cloturer', methods=['POST'])
@role_required('ingenieur', 'admin')
def cloturer_projet(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.ingenieur_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Accès refusé'}), 403
    p.statut = 'cloture'; p.date_cloture = datetime.utcnow()
    if p.ingenieur: p.ingenieur.nb_projets_termines += 1
    create_notification(p.client_id, '🎉 Projet clôturé!', f"'{p.titre}' est officiellement terminé.", 'succes')
    db.session.commit()
    return jsonify({'message': 'Projet clôturé'})


# ═══════════════════════════════════════
#  CONTRATS
# ═══════════════════════════════════════
@app.route('/api/projets/<int:pid>/contrat', methods=['GET'])
@login_required
def get_contrat(pid):
    c = Contrat.query.filter_by(projet_id=pid).first_or_404()
    return jsonify(c.to_dict())


@app.route('/api/projets/<int:pid>/contrat/accepter', methods=['POST'])
@role_required('client')
def accepter_contrat(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.client_id != user.id: return jsonify({'error': 'Accès refusé'}), 403
    c = Contrat.query.filter_by(projet_id=pid).first_or_404()
    c.statut = 'signe'; c.date_signature = datetime.utcnow()
    p.statut = 'en_cours'
    create_notification(p.ingenieur_id, '📝 Contrat signé!', f"Contrat signé pour '{p.titre}'.", 'succes')
    db.session.commit()
    return jsonify({'message': 'Contrat accepté', 'contrat': c.to_dict()})


# ═══════════════════════════════════════
#  PAIEMENTS
# ═══════════════════════════════════════
@app.route('/api/projets/<int:pid>/paiements', methods=['GET'])
@login_required
def get_paiements(pid):
    return jsonify([p.to_dict() for p in Paiement.query.filter_by(projet_id=pid).all()])


@app.route('/api/projets/<int:pid>/paiements', methods=['POST'])
@role_required('client')
def effectuer_paiement(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.client_id != user.id: return jsonify({'error': 'Accès refusé'}), 403
    data = request.json or {}
    if not data.get('montant') or not data.get('type'):
        return jsonify({'error': 'Montant et type requis'}), 400
    pay = Paiement(reference=gen_reference('PAY', Paiement), projet_id=pid,
                   montant=float(data['montant']), type_paiement=data['type'],
                   methode=data.get('methode', 'carte'), statut='effectue',
                   notes=data.get('notes', ''), date_paiement=datetime.utcnow())
    db.session.add(pay)
    create_notification(p.ingenieur_id, '💰 Paiement reçu!',
                        f"Paiement {data['type']} de {data['montant']} DT pour '{p.titre}'.", 'succes')
    db.session.commit()
    return jsonify({'message': 'Paiement effectué', 'paiement': pay.to_dict()}), 201


# ═══════════════════════════════════════
#  MESSAGES
# ═══════════════════════════════════════
@app.route('/api/projets/<int:pid>/messages', methods=['GET'])
@login_required
def get_messages(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.client_id != user.id and p.ingenieur_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Accès refusé'}), 403
    Message.query.filter_by(projet_id=pid, lu=False).filter(
        Message.expediteur_id != user.id).update({'lu': True})
    db.session.commit()
    return jsonify([m.to_dict() for m in Message.query.filter_by(projet_id=pid).order_by(Message.date_envoi).all()])


@app.route('/api/projets/<int:pid>/messages', methods=['POST'])
@login_required
def send_message(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.client_id != user.id and p.ingenieur_id != user.id:
        return jsonify({'error': 'Accès refusé'}), 403

    fichier_url = ''; type_msg = 'texte'
    if 'fichier' in request.files:
        f = request.files['fichier']
        if f:
            ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else ''
            fichier_url = save_file(f, 'msg')
            type_msg = 'image' if ext in ALLOWED_EXTENSIONS else 'fichier'

    is_mp = request.content_type and 'multipart' in request.content_type
    data = request.form if is_mp else (request.json or {})
    contenu = data.get('contenu', '') or fichier_url
    if not contenu: return jsonify({'error': 'Contenu vide'}), 400

    msg = Message(projet_id=pid, expediteur_id=user.id, contenu=contenu,
                  type_msg=type_msg, fichier_url=fichier_url)
    db.session.add(msg)
    dest_id = p.ingenieur_id if user.id == p.client_id else p.client_id
    create_notification(dest_id, '💬 Nouveau message',
                        f"{user.prenom}: {contenu[:60]}", 'info')
    db.session.commit()
    return jsonify(msg.to_dict()), 201


# ═══════════════════════════════════════
#  RÉVISIONS
# ═══════════════════════════════════════
@app.route('/api/projets/<int:pid>/revisions', methods=['GET'])
@login_required
def get_revisions(pid):
    return jsonify([r.to_dict() for r in Revision.query.filter_by(projet_id=pid).order_by(Revision.date_demande.desc()).all()])


@app.route('/api/projets/<int:pid>/revisions', methods=['POST'])
@role_required('client')
def demander_revision(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    data = request.json or {}
    if not data.get('description'): return jsonify({'error': 'Description requise'}), 400
    rev = Revision(projet_id=pid, demandeur_id=user.id, description=data['description'],
                   priorite=data.get('priorite', 'normale'))
    db.session.add(rev)
    p.statut = 'en_revision'
    create_notification(p.ingenieur_id, '🔄 Révision demandée',
                        f"{data['description'][:80]}", 'alerte')
    db.session.commit()
    return jsonify({'message': 'Révision demandée', 'revision': rev.to_dict()}), 201


@app.route('/api/revisions/<int:rid>/traiter', methods=['POST'])
@role_required('ingenieur')
def traiter_revision(rid):
    rev = Revision.query.get_or_404(rid)
    rev.statut = 'termine'; rev.date_traitement = datetime.utcnow()
    p = rev.projet
    if not Revision.query.filter_by(projet_id=p.id, statut='en_attente').first():
        p.statut = 'en_cours'
    db.session.commit()
    return jsonify({'message': 'Révision traitée'})


# ═══════════════════════════════════════
#  NOTIFICATIONS
# ═══════════════════════════════════════
@app.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    user = get_current_user()
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.date_creation.desc()).limit(20).all()
    non_lues = Notification.query.filter_by(user_id=user.id, lue=False).count()
    return jsonify({'non_lues': non_lues, 'items': [n.to_dict() for n in notifs]})


@app.route('/api/notifications/lire', methods=['POST'])
@login_required
def mark_read():
    user = get_current_user()
    Notification.query.filter_by(user_id=user.id, lue=False).update({'lue': True})
    db.session.commit()
    return jsonify({'message': 'Lu'})


# ═══════════════════════════════════════
#  AVIS
# ═══════════════════════════════════════
@app.route('/api/projets/<int:pid>/avis', methods=['POST'])
@role_required('client')
def donner_avis(pid):
    user = get_current_user()
    p = Projet.query.get_or_404(pid)
    if p.client_id != user.id: return jsonify({'error': 'Accès refusé'}), 403
    if p.statut not in ('valide', 'cloture'):
        return jsonify({'error': 'Projet pas encore terminé'}), 400
    data = request.json or {}
    note = int(data.get('note', 0))
    if not 1 <= note <= 5: return jsonify({'error': 'Note entre 1 et 5'}), 400
    avis = Avis(projet_id=pid, client_id=user.id, ingenieur_id=p.ingenieur_id,
                note=note, commentaire=data.get('commentaire', ''))
    db.session.add(avis)
    all_avis = Avis.query.filter_by(ingenieur_id=p.ingenieur_id).all() + [avis]
    p.ingenieur.note_moyenne = round(sum(a.note for a in all_avis) / len(all_avis), 2)
    db.session.commit()
    return jsonify({'message': 'Avis enregistré', 'note_moyenne': p.ingenieur.note_moyenne}), 201


# ═══════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════
@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    user = get_current_user()
    non_lues = Notification.query.filter_by(user_id=user.id, lue=False).count()
    if user.role == 'client':
        projets = Projet.query.filter_by(client_id=user.id).all()
        all_pays = [pay for p in projets for pay in p.paiements if pay.statut == 'effectue']
        msgs_non_lus = Message.query.join(Projet).filter(
            Projet.client_id == user.id, Message.lu == False,
            Message.expediteur_id != user.id).count()
        return jsonify({
            'projets_total': len(projets),
            'projets_actifs': sum(1 for p in projets if p.statut == 'en_cours'),
            'projets_termines': sum(1 for p in projets if p.statut in ('valide','cloture')),
            'projets_revision': sum(1 for p in projets if p.statut == 'en_revision'),
            'budget_total': sum(p.budget_estime for p in projets),
            'total_paye': sum(p.montant for p in all_pays),
            'messages_non_lus': msgs_non_lus,
            'notifications_non_lues': non_lues,
        })
    elif user.role == 'ingenieur':
        projets = Projet.query.filter_by(ingenieur_id=user.id).all()
        revisions_att = Revision.query.join(Projet).filter(
            Projet.ingenieur_id == user.id, Revision.statut == 'en_attente').count()
        msgs_non_lus = Message.query.join(Projet).filter(
            Projet.ingenieur_id == user.id, Message.lu == False,
            Message.expediteur_id != user.id).count()
        return jsonify({
            'projets_total': len(projets),
            'projets_actifs': sum(1 for p in projets if p.statut == 'en_cours'),
            'projets_termines': user.nb_projets_termines,
            'projets_revision': sum(1 for p in projets if p.statut == 'en_revision'),
            'note_moyenne': user.note_moyenne,
            'nb_conceptions': sum(1 for c in user.conceptions if c.statut == 'publie'),
            'revisions_en_attente': revisions_att,
            'messages_non_lus': msgs_non_lus,
            'notifications_non_lues': non_lues,
        })
    return jsonify({})


# ═══════════════════════════════════════
#  SEED
# ═══════════════════════════════════════
def seed_data():
    if Utilisateur.query.count() > 0:
        return

    styles_data = [
        ('Moderne','Lignes épurées, grandes baies vitrées, toits plats. Fusion entre fonctionnalité et esthétique contemporaine.','🏢','linear-gradient(135deg,#1a2570,#2563eb)','Populaire'),
        ('Minimaliste','Moins c\'est plus. Espaces ouverts, palette neutre, chaque élément a sa raison d\'être.','🏠','linear-gradient(135deg,#0a0f2e,#1e3a8a)',''),
        ('Contemporain','Design actuel qui évolue avec les tendances. Mélange audacieux de textures et matières naturelles.','🏗️','linear-gradient(135deg,#0d1547,#06b6d4)','Nouveau'),
        ('Méditerranéen','Toits en tuiles, arcades, couleurs chaudes. L\'âme du bassin méditerranéen dans votre demeure.','🏛️','linear-gradient(135deg,#1a0a0a,#7c2d12)',''),
        ('Art Déco','Géométrie élaborée, matériaux luxueux, symétrie parfaite. Élégance intemporelle des années folles.','🏯','linear-gradient(135deg,#1a1505,#92400e)','Premium'),
        ('Industriel','Béton brut, acier exposé, loft ouvert. Urbain qui transforme l\'utilitaire en œuvre d\'art.','🏭','linear-gradient(135deg,#111827,#374151)',''),
        ('Néo-Classique','Réinterprétation moderne des canons classiques. Colonnes, frontons et symétrie revisités.','🏰','linear-gradient(135deg,#1a0e2e,#4c1d95)',''),
        ('Bioclimatique','Architecture durable intégrée à l\'environnement. Énergie passive, matériaux naturels.','🌿','linear-gradient(135deg,#052e16,#166534)','Éco'),
    ]
    styles = []
    for nom, desc, emoji, bg, badge in styles_data:
        s = StyleArchitectural(nom=nom, description=desc, emoji=emoji, couleur_bg=bg, badge=badge)
        db.session.add(s); styles.append(s)
    db.session.flush()

    admin = Utilisateur(nom='Admin', prenom='System', email='admin@buildsmart.tn',
                        mot_de_passe=generate_password_hash('admin123'), role='admin', ville='Tunis')
    client1 = Utilisateur(nom='Mansour', prenom='Aziz', email='client@demo.com',
                          mot_de_passe=generate_password_hash('1234'), role='client',
                          telephone='+216 55 123 456', ville='Tunis',
                          bio='Propriétaire cherchant une villa moderne pour ma famille.')
    client2 = Utilisateur(nom='Riahi', prenom='Sara', email='sara@demo.com',
                          mot_de_passe=generate_password_hash('1234'), role='client',
                          telephone='+216 22 987 654', ville='Sfax',
                          bio='À la recherche d\'un appartement contemporain élégant.')
    ing1 = Utilisateur(nom='Ben Ali', prenom='Sami', email='ing@demo.com',
                       mot_de_passe=generate_password_hash('1234'), role='ingenieur',
                       telephone='+216 98 456 789', ville='Tunis',
                       bio='Architecte senior avec 12 ans d\'expérience. Spécialisé en style moderne et minimaliste.',
                       specialites=json.dumps(['Moderne','Minimaliste','Contemporain']),
                       experience_ans=12, note_moyenne=4.9, nb_projets_termines=47, tarif_horaire=80.0)
    ing2 = Utilisateur(nom='Trabelsi', prenom='Leila', email='leila@demo.com',
                       mot_de_passe=generate_password_hash('1234'), role='ingenieur',
                       telephone='+216 71 234 567', ville='Sousse',
                       bio='Architecte passionnée par le style méditerranéen et l\'Art Déco. 8 ans d\'expérience.',
                       specialites=json.dumps(['Méditerranéen','Art Déco','Néo-Classique']),
                       experience_ans=8, note_moyenne=4.7, nb_projets_termines=28, tarif_horaire=65.0)
    ing3 = Utilisateur(nom='Nasri', prenom='Karim', email='karim@demo.com',
                       mot_de_passe=generate_password_hash('1234'), role='ingenieur',
                       telephone='+216 52 789 012', ville='Tunis',
                       bio='Expert en architecture bioclimatique. Fort engagement pour le développement durable.',
                       specialites=json.dumps(['Bioclimatique','Industriel','Minimaliste']),
                       experience_ans=6, note_moyenne=4.8, nb_projets_termines=19,
                       tarif_horaire=70.0, disponible=False)
    db.session.add_all([admin, client1, client2, ing1, ing2, ing3])
    db.session.flush()

    conceptions_raw = [
        (ing1.id, 0, 'Villa Lumière', 'Villa contemporaine baignée de lumière naturelle. Grandes baies vitrées sud, toit-terrasse avec pergola, jardin paysager.', 850, 180, 320, 4, 2, ['Baies vitrées XXL','Toit terrasse','Pergola','Jardin paysager','Double garage','Piscine optionnelle'], 187, 42),
        (ing1.id, 1, 'Maison Zéro',  'Design minimaliste radical. Volumes purs, palette monochrome béton-blanc, espaces fluides sans cloisons inutiles.', 720, 120, 200, 3, 1, ['Toit plat végétalisé','Béton ciré','Domotique','Fenêtres bandeau','Porte pivot inox'], 134, 28),
        (ing1.id, 2, 'Sky Loft',     'Duplex contemporain avec verrière zénithale spectaculaire. Mezzanine ouverte, cuisine îlot, terrasse panoramique 40m².', 950, 90, 150, 2, 2, ['Verrière zénithale','Mezzanine','Terrasse panoramique','Cuisine îlot','Escalier flottant'], 210, 55),
        (ing2.id, 3, 'Casa Andalucia','Villa méditerranéenne avec patio central fontaine, arcades pierre, tuiles terre cuite.', 780, 200, 400, 5, 2, ['Patio central','Fontaine','Arcades pierre','Tuiles terre cuite','Pergola vigne','Piscine traditionnelle'], 156, 38),
        (ing2.id, 4, 'Palais Art Déco','Résidence de prestige. Façade marbre, verrières géométriques, ferronneries dorées.', 1400, 300, 600, 6, 3, ['Façade marbre','Ferronneries dorées','Verrières géométriques','Hall monumental','Bibliothèque boiseries','Cave à vins'], 89, 21),
        (ing3.id, 7, 'EcoHaus',      'Maison bioclimatique certifiée BBC. Murs pisé, toiture végétalisée, 0 facture énergétique.', 680, 100, 180, 3, 1, ['Toiture végétalisée','Panneaux solaires','Murs pisé','Récupération eau','Pompe à chaleur','Certification BBC'], 178, 47),
        (ing3.id, 5, 'Urban Factory', 'Loft industriel brut. Béton apparent, poutres métal, briques rouges, hauteur 4m.', 700, 80, 140, 1, 1, ['Béton apparent','Poutres métal','Briques rouges','Hauteur 4m','Escalier métal','Baies industrielles'], 143, 33),
        (ing1.id, 6, 'Néo-Haussmann', 'Réinterprétation moderne Haussmannien. Façade pierre blonde, balcons filants, parquet point de Hongrie.', 1100, 150, 280, 4, 4, ['Pierre blonde','Balcons filants','Parquet Hongrie','Cheminées','Moulures plâtre','Cave voûtée'], 201, 61),
    ]
    for ing_id, s_idx, titre, desc, prix, smin, smax, ch, et, carac, vues, likes in conceptions_raw:
        db.session.add(Conception(
            titre=titre, description=desc, style_id=styles[s_idx].id,
            statut='publie', prix_base=prix, superficie_min=smin, superficie_max=smax,
            nb_chambres=ch, nb_etages=et, caracteristiques=json.dumps(carac),
            images=json.dumps([]), ingenieur_id=ing_id, nb_vues=vues, nb_likes=likes))
    db.session.flush()

    conceptions = Conception.query.all()
    proj1 = Projet(reference='PRJ-2025-0001', titre='Villa Moderne - Tunis Nord',
                   description='Construction villa moderne 250m² avec piscine. Style contemporain, grandes ouvertures.',
                   adresse='Rue des Oliviers, La Marsa', ville='Tunis', superficie=250,
                   budget_estime=1200, priorite='haute', statut='en_cours', progression=75,
                   notes_client='Maximiser lumière naturelle. Budget flexible si qualité.',
                   client_id=client1.id, ingenieur_id=ing1.id, conception_id=conceptions[0].id,
                   date_fin_prevue=datetime.utcnow()+timedelta(days=90))
    proj2 = Projet(reference='PRJ-2025-0002', titre='Appartement Contemporain - Sfax',
                   description='Rénovation complète 120m² style contemporain.',
                   adresse='Avenue Farhat Hached', ville='Sfax', superficie=120,
                   budget_estime=950, priorite='normale', statut='en_revision', progression=90,
                   notes_client='Priorité aux matériaux locaux et durables.',
                   client_id=client2.id, ingenieur_id=ing2.id, conception_id=conceptions[2].id,
                   date_fin_prevue=datetime.utcnow()+timedelta(days=30))
    proj3 = Projet(reference='PRJ-2024-0015', titre='Maison Bioclimatique - La Soukra',
                   description='Construction neuve bioclimatique certification BBC.',
                   adresse='Cité El Mourouj', ville='Tunis', superficie=160,
                   budget_estime=830, priorite='normale', statut='cloture', progression=100,
                   client_id=client1.id, ingenieur_id=ing3.id, conception_id=conceptions[5].id,
                   date_fin_prevue=datetime.utcnow()-timedelta(days=10),
                   date_cloture=datetime.utcnow()-timedelta(days=5))
    db.session.add_all([proj1, proj2, proj3])
    db.session.flush()

    for proj, montant in [(proj1,1350),(proj2,1150),(proj3,1030)]:
        db.session.add(Contrat(numero=f"CTR-2025-{proj.id:04d}", projet_id=proj.id,
                               montant_total=montant, montant_initial=round(montant*.5,2),
                               montant_final=round(montant*.5,2), statut='signe',
                               conditions='Contrat conception architecturale. Révisions incluses. Paiement 50/50.',
                               date_signature=datetime.utcnow()-timedelta(days=30),
                               date_expiration=datetime.utcnow()+timedelta(days=180)))

    for ref,pid,m,t,meth,jours in [('PAY-2025-0001',proj1.id,675,'initial','virement',25),
                                    ('PAY-2025-0002',proj2.id,575,'initial','carte',15),
                                    ('PAY-2024-0015',proj3.id,515,'initial','carte',60),
                                    ('PAY-2024-0016',proj3.id,515,'final','virement',5)]:
        db.session.add(Paiement(reference=ref,projet_id=pid,montant=m,type_paiement=t,
                                methode=meth,statut='effectue',date_paiement=datetime.utcnow()-timedelta(days=jours)))

    for pid,eid,contenu,typ in [
        (proj1.id,ing1.id,"Bonjour Aziz! Les premières esquisses de votre villa sont prêtes. Plans préliminaires disponibles pour revue.",'texte'),
        (proj1.id,client1.id,"Merci Sami! Possible d'agrandir le séjour et ajouter une terrasse côté jardin?",'texte'),
        (proj1.id,ing1.id,"Absolument! Séjour agrandi de 20m² + terrasse 30m² sur jardin. Nouvelle version sous 48h.",'texte'),
        (proj1.id,client1.id,"Parfait! 🙏 Concernant la piscine, quelle dimension pour le terrain disponible?",'texte'),
        (proj1.id,ing1.id,"Pour 600m² de terrain, je recommande une piscine 10x5m en L. Espace optimal pour le jardin.",'texte'),
        (proj2.id,ing2.id,"Bonjour Sara! Plans de révision finalisés. Réunion vendredi pour commenter?",'texte'),
        (proj2.id,client2.id,"Oui, disponible vendredi matin. Les modifications ont bien été intégrées?",'texte'),
        (proj2.id,ing2.id,"Tout à fait! Salle de bain agrandie, cuisine ouverte sur séjour, rangements optimisés.",'texte'),
    ]:
        db.session.add(Message(projet_id=pid,expediteur_id=eid,contenu=contenu,type_msg=typ,lu=True))

    db.session.add(Revision(projet_id=proj1.id,demandeur_id=client1.id,
                             description="Agrandir salon de 15m² et déplacer cuisine vers aile nord pour meilleure orientation.",
                             statut='termine',priorite='normale',date_traitement=datetime.utcnow()-timedelta(days=5)))
    db.session.add(Revision(projet_id=proj2.id,demandeur_id=client2.id,
                             description="Salle de bain principale minimum 12m². Douche italienne + baignoire séparée.",
                             statut='en_attente',priorite='haute'))

    db.session.add(Avis(projet_id=proj3.id,client_id=client1.id,ingenieur_id=ing3.id,
                        note=5,commentaire="Karim est exceptionnel! Professionnel, à l'écoute, créatif. Résultat dépasse toutes nos attentes!"))

    for u in [client1,client2,ing1,ing2,ing3]:
        db.session.add(Notification(user_id=u.id,titre='Bienvenue sur BuildSmart! 🎉',
                                    contenu=f'Bonjour {u.prenom}, compte prêt.',type_notif='succes'))
    db.session.add(Notification(user_id=client1.id,titre='📊 Progression: 75%',
                                contenu="Projet 'Villa Moderne' à 75% d'avancement.",type_notif='info'))
    db.session.add(Notification(user_id=ing1.id,titre='💰 Paiement reçu!',
                                contenu="Paiement initial 675 DT pour 'Villa Moderne - Tunis Nord'.",type_notif='succes'))

    ing3.nb_projets_termines = 1
    db.session.commit()
    print("✅ Seed data complet!")


# ═══════════════════════════════════════
#  MESSAGES DIRECTS (REST API)
# ═══════════════════════════════════════

@app.route('/api/dm/conversations', methods=['GET'])
@login_required
def get_conversations():
    """List all users I have exchanged DMs with, plus unread count."""
    user = get_current_user()
    uid = user.id
    # Get distinct conversation partners
    sent = db.session.query(MessageDirect.destinataire_id).filter_by(expediteur_id=uid)
    recv = db.session.query(MessageDirect.expediteur_id).filter_by(destinataire_id=uid)
    partner_ids = {r[0] for r in sent.union(recv).all()}

    conversations = []
    for pid in partner_ids:
        partner = Utilisateur.query.get(pid)
        if not partner:
            continue
        last_msg = MessageDirect.query.filter(
            db.or_(
                db.and_(MessageDirect.expediteur_id==uid, MessageDirect.destinataire_id==pid),
                db.and_(MessageDirect.expediteur_id==pid, MessageDirect.destinataire_id==uid)
            )
        ).order_by(MessageDirect.date_envoi.desc()).first()
        unread = MessageDirect.query.filter_by(expediteur_id=pid, destinataire_id=uid, lu=False).count()
        conversations.append({
            'partner_id': pid,
            'partner_nom': f"{partner.prenom} {partner.nom}",
            'partner_initiales': (partner.prenom[0]+partner.nom[0]).upper(),
            'partner_avatar': partner.avatar,
            'partner_role': partner.role,
            'online': pid in online_users,
            'unread': unread,
            'last_message': last_msg.contenu[:60] if last_msg else '',
            'last_date': last_msg.date_envoi.strftime('%d/%m %H:%M') if last_msg else '',
        })
    conversations.sort(key=lambda x: x['last_date'], reverse=True)
    return jsonify(conversations)


@app.route('/api/dm/<int:partner_id>', methods=['GET'])
@login_required
def get_dm_history(partner_id):
    """Get full chat history with a user and mark as read."""
    user = get_current_user()
    uid = user.id
    msgs = MessageDirect.query.filter(
        db.or_(
            db.and_(MessageDirect.expediteur_id==uid, MessageDirect.destinataire_id==partner_id),
            db.and_(MessageDirect.expediteur_id==partner_id, MessageDirect.destinataire_id==uid)
        )
    ).order_by(MessageDirect.date_envoi).all()
    # Mark incoming as read
    MessageDirect.query.filter_by(expediteur_id=partner_id, destinataire_id=uid, lu=False).update({'lu': True})
    db.session.commit()
    return jsonify([m.to_dict() for m in msgs])


@app.route('/api/dm/<int:partner_id>', methods=['POST'])
@login_required
def send_dm(partner_id):
    """Send a DM via REST (fallback — Socket.IO is preferred)."""
    user = get_current_user()
    data = request.json or {}
    contenu = data.get('contenu', '').strip()
    if not contenu:
        return jsonify({'error': 'Contenu vide'}), 400
    partner = Utilisateur.query.get_or_404(partner_id)
    msg = MessageDirect(expediteur_id=user.id, destinataire_id=partner_id, contenu=contenu)
    db.session.add(msg)
    create_notification(partner_id, f'💬 Message de {user.prenom}', contenu[:60], 'info')
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@app.route('/api/dm/unread-count', methods=['GET'])
@login_required
def dm_unread_count():
    user = get_current_user()
    count = MessageDirect.query.filter_by(destinataire_id=user.id, lu=False).count()
    return jsonify({'count': count})


@app.route('/api/users', methods=['GET'])
@login_required
def list_users():
    """List all users available to chat with (everyone except self)."""
    user = get_current_user()
    users = Utilisateur.query.filter(Utilisateur.id != user.id, Utilisateur.actif == True).all()
    result = []
    for u in users:
        d = u.to_dict()
        d['online'] = u.id in online_users
        result.append(d)
    return jsonify(result)


# ═══════════════════════════════════════
#  SOCKET.IO — REAL-TIME EVENTS
# ═══════════════════════════════════════

def get_room(uid1, uid2):
    """Deterministic room name for two users."""
    return f"dm_{min(uid1,uid2)}_{max(uid1,uid2)}"


# sid → user_id map (since session is unreliable over WebSocket)
sid_to_uid = {}

@socketio.on('connect')
def on_connect():
    pass  # user registers via 'register_user' event after connect


@socketio.on('register_user')
def on_register_user(data):
    """Client sends their user_id right after connecting."""
    uid = data.get('user_id')
    if uid:
        sid_to_uid[request.sid] = uid
        online_users[uid] = request.sid
        emit('online_status', {'user_id': uid, 'online': True}, broadcast=True)


@socketio.on('disconnect')
def on_disconnect():
    uid = sid_to_uid.pop(request.sid, None)
    if uid and uid in online_users:
        del online_users[uid]
        emit('online_status', {'user_id': uid, 'online': False}, broadcast=True)


@socketio.on('join_dm')
def on_join_dm(data):
    uid = sid_to_uid.get(request.sid)
    partner_id = data.get('partner_id')
    if uid and partner_id:
        room = get_room(uid, partner_id)
        join_room(room)
        emit('joined_room', {'room': room})


@socketio.on('leave_dm')
def on_leave_dm(data):
    uid = sid_to_uid.get(request.sid)
    partner_id = data.get('partner_id')
    if uid and partner_id:
        leave_room(get_room(uid, partner_id))


@socketio.on('send_dm')
def on_send_dm(data):
    uid = sid_to_uid.get(request.sid)
    partner_id = data.get('partner_id')
    contenu = (data.get('contenu') or '').strip()
    if not uid or not partner_id or not contenu:
        return
    msg = MessageDirect(expediteur_id=uid, destinataire_id=partner_id, contenu=contenu)
    db.session.add(msg)
    create_notification(partner_id, '💬 Nouveau message', contenu[:60], 'info')
    db.session.commit()
    msg_dict = msg.to_dict()
    room = get_room(uid, partner_id)
    emit('new_dm', msg_dict, room=room)
    if partner_id in online_users:
        emit('dm_notification', {'from_id': uid, 'contenu': contenu[:60]},
             to=online_users[partner_id])


@socketio.on('typing')
def on_typing(data):
    uid = sid_to_uid.get(request.sid)
    partner_id = data.get('partner_id')
    if uid and partner_id:
        room = get_room(uid, partner_id)
        emit('user_typing', {'user_id': uid, 'typing': data.get('typing', False)},
             room=room, include_self=False)


# ═══════════════════════════════════════
# SOCKET.IO — PROJECT CHAT (real-time)
# ═══════════════════════════════════════

@socketio.on('join_project')
def on_join_project(data):
    uid = sid_to_uid.get(request.sid)
    pid = data.get('projet_id')
    if pid:
        join_room(f"projet_{pid}")
        emit('joined_project', {'projet_id': pid})


@socketio.on('send_project_message')
def on_send_project_message(data):
    uid = sid_to_uid.get(request.sid)
    pid = data.get('projet_id')
    contenu = (data.get('contenu') or '').strip()
    if not uid or not pid or not contenu:
        emit('error', {'msg': 'not authenticated or missing data'})
        return
    user = Utilisateur.query.get(uid)
    p = Projet.query.get(pid)
    if not p or not user:
        return
    if p.client_id != uid and p.ingenieur_id != uid and user.role != 'admin':
        return
    msg = Message(projet_id=pid, expediteur_id=uid, contenu=contenu, type_msg='texte')
    db.session.add(msg)
    dest_id = p.ingenieur_id if uid == p.client_id else p.client_id
    if dest_id:
        create_notification(dest_id, '💬 Nouveau message', f"{user.prenom}: {contenu[:60]}", 'info')
    db.session.commit()
    emit('new_project_message', msg.to_dict(), room=f"projet_{pid}")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    socketio.run(app, debug=True, port=5000)
