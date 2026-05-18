from flask import Blueprint, request, jsonify
from .models import User, Category, Professional, Review
from . import db
from datetime import datetime, timezone, timedelta
from functools import wraps
import jwt
import os
import uuid
import unicodedata
import re
import time
import requests as http_requests
from jose import jwt as jose_jwt

api = Blueprint('api', __name__, url_prefix='/')

SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key')


def generate_slug(name):
    slug = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    slug = slug.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug


def generate_uuid():
    return str(uuid.uuid4())


def create_access_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def create_refresh_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'code': 'MISSING_TOKEN', 'message': 'Authentication token is missing'}), 401

        try:
            jwks = get_clerk_jwks()
            payload = jose_jwt.decode(token, jwks, algorithms=['RS256'], options={'verify_aud': False})
        except Exception:
            return jsonify({'code': 'INVALID_TOKEN', 'message': 'Invalid token'}), 401

        email = payload.get('email', '')
        if not email:
            return jsonify({'code': 'MISSING_EMAIL', 'message': 'Token missing email claim'}), 401

        current_user = User.query.filter_by(email=email).first()
        if not current_user:
            name = payload.get('name') or email.split('@')[0]
            avatar = payload.get('image_url', '')
            current_user = User(id=generate_uuid(), email=email, name=name, role='client', avatar_url=avatar)
            db.session.add(current_user)
            db.session.commit()

        return f(current_user, *args, **kwargs)
    return decorated


def serialize_user(user):
    return {
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'role': user.role,
        'avatarUrl': user.avatar_url,
        'phone': user.phone,
        'address': {
            'state': user.address_state,
            'city': user.address_city,
            'district': user.address_district,
            'street': user.address_street,
            'number': user.address_number
        } if any([user.address_state, user.address_city, user.address_district, user.address_street, user.address_number]) else None,
        'createdAt': user.created_at.isoformat() if user.created_at else None
    }


def serialize_category(category):
    return {
        'id': category.id,
        'name': category.name,
        'slug': category.slug,
        'icon': category.icon
    }


def serialize_professional(professional, include_full=False):
    data = {
        'id': professional.id,
        'userId': professional.user_id,
        'slug': professional.slug,
        'name': professional.name,
        'title': professional.title,
        'avatarUrl': professional.avatar_url,
        'state': professional.state,
        'city': professional.city,
        'rating': professional.rating,
        'reviewsCount': professional.reviews_count,
        'categories': [c.name for c in professional.categories]
    }

    if include_full:
        data.update({
            'description': professional.description,
            'phone': professional.phone,
            'email': professional.email,
            'instagram': professional.instagram,
            'website': professional.website,
            'registrationNumber': professional.registration_number,
            'address': {
                'state': professional.state,
                'city': professional.city,
                'district': professional.district
            },
            'district': professional.district,
            'reviews': [serialize_review(r) for r in professional.reviews[:10]],
            'categories': [serialize_category(c) for c in professional.categories],
            'verified': professional.verified,
            'available': professional.available,
            'createdAt': professional.created_at.isoformat() if professional.created_at else None
        })

    return data


def serialize_review(review):
    return {
        'id': review.id,
        'userName': review.user_name,
        'userAvatarUrl': review.user_avatar_url,
        'rating': review.rating,
        'comment': review.comment,
        'createdAt': review.created_at.isoformat() if review.created_at else None
    }


def paginate_query(query, page, limit):
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {
        'data': items,
        'meta': {
            'page': page,
            'limit': limit,
            'total': total,
            'totalPages': (total + limit - 1) // limit if limit > 0 else 0
        }
    }


_jwks_cache: dict = {'keys': None, 'expires': 0.0}


def get_clerk_jwks() -> dict:
    if _jwks_cache['expires'] > time.time():
        return _jwks_cache['keys']
    jwks_url = os.getenv('CLERK_JWKS_URL', '')
    if not jwks_url:
        raise ValueError('CLERK_JWKS_URL not configured')
    resp = http_requests.get(jwks_url, timeout=5)
    resp.raise_for_status()
    keys = resp.json()
    _jwks_cache['keys'] = keys
    _jwks_cache['expires'] = time.time() + 3600
    return keys


@api.route('/auth/clerk', methods=['POST'])
def clerk_auth():
    data = request.get_json()
    if not data or 'clerkToken' not in data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'clerkToken is required'}), 400

    clerk_token = data.get('clerkToken')
    user_type = data.get('userType', 'client')

    try:
        jwks = get_clerk_jwks()
        payload = jose_jwt.decode(
            clerk_token,
            jwks,
            algorithms=['RS256'],
            options={'verify_aud': False},
        )
    except Exception as e:
        return jsonify({'code': 'INVALID_TOKEN', 'message': 'Invalid Clerk token'}), 401

    email = payload.get('email', '')
    name = payload.get('name') or (email.split('@')[0] if email else 'Usuário')
    avatar_url = payload.get('image_url', '')

    if not email:
        return jsonify({'code': 'MISSING_EMAIL', 'message': 'Token missing email claim'}), 401

    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            id=generate_uuid(),
            email=email,
            name=name,
            role=user_type,
            avatar_url=avatar_url,
        )
        db.session.add(user)
        db.session.commit()

        if user_type == 'professional':
            slug_base = generate_slug(name)
            slug = slug_base
            counter = 1
            while Professional.query.filter_by(slug=slug).first():
                slug = f"{slug_base}-{counter}"
                counter += 1

            professional = Professional(
                id=generate_uuid(),
                user_id=user.id,
                slug=slug,
                name=name,
                state=user.address_state,
                city=user.address_city,
                district=user.address_district,
            )
            db.session.add(professional)
            db.session.commit()

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return jsonify({
        'user': serialize_user(user),
        'access_token': access_token,
        'refresh_token': refresh_token,
    }), 200


@api.route('/auth/google', methods=['POST'])
def google_auth():
    data = request.get_json()
    if not data or 'googleToken' not in data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'googleToken is required'}), 401

    google_token = data.get('googleToken')
    user_type = data.get('userType', 'client')

    try:
        import google.oauth2.id_token
        from google.auth.transport import requests as google_requests
        idinfo = google.oauth2.id_token.verify_oauth2_token(google_token, google_requests.Request())
        email = idinfo.get('email')
        name = idinfo.get('name')
        avatar_url = idinfo.get('picture')
    except Exception:
        return jsonify({'code': 'INVALID_TOKEN', 'message': 'Invalid Google token'}), 401

    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            id=generate_uuid(),
            email=email,
            name=name,
            role=user_type,
            avatar_url=avatar_url
        )
        db.session.add(user)
        db.session.commit()

        if user_type == 'professional':
            slug_base = generate_slug(name)
            slug = slug_base
            counter = 1
            while Professional.query.filter_by(slug=slug).first():
                slug = f"{slug_base}-{counter}"
                counter += 1

            professional = Professional(
                id=generate_uuid(),
                user_id=user.id,
                slug=slug,
                name=name,
                state=user.address_state,
                city=user.address_city,
                district=user.address_district
            )
            db.session.add(professional)
            db.session.commit()

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return jsonify({
        'user': serialize_user(user),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@api.route('/auth/refresh', methods=['POST'])
def refresh_token():
    data = request.get_json()
    if not data or 'refresh_token' not in data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'refresh_token is required'}), 401

    try:
        token_data = jwt.decode(data['refresh_token'], SECRET_KEY, algorithms=['HS256'])
        user = User.query.get(token_data['user_id'])
        if not user:
            return jsonify({'code': 'USER_NOT_FOUND', 'message': 'User not found'}), 401

        new_access_token = create_access_token(user.id, user.role)
        new_refresh_token = create_refresh_token(user.id)

        return jsonify({
            'access_token': new_access_token,
            'refresh_token': new_refresh_token
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'code': 'TOKEN_EXPIRED', 'message': 'Refresh token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'code': 'INVALID_TOKEN', 'message': 'Invalid refresh token'}), 401


@api.route('/categories', methods=['GET'])
def list_categories():
    include_inactive = request.args.get('includeInactive', 'false').lower() == 'true'
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    query = Category.query
    if not include_inactive:
        query = query.filter_by(is_active=True)

    query = query.order_by(Category.name)
    result = paginate_query(query, page, limit)

    return jsonify({
        'data': [serialize_category(c) for c in result['data']],
        'meta': result['meta']
    }), 200


@api.route('/professionals/featured', methods=['GET'])
def list_featured_professionals():
    professionals = Professional.query.filter_by(featured=True, available=True).all()
    return jsonify([serialize_professional(p) for p in professionals]), 200


@api.route('/professionals/slug/<slug>', methods=['GET'])
def get_professional_by_slug(slug):
    professional = Professional.query.filter_by(slug=slug).first()
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional not found'}), 404

    return jsonify(serialize_professional(professional, include_full=True)), 200


@api.route('/professionals/<id>/reviews', methods=['GET'])
def list_professional_reviews(id):
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    professional = Professional.query.get(id)
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional not found'}), 404

    query = Review.query.filter_by(professional_id=id).order_by(Review.created_at.desc())
    result = paginate_query(query, page, limit)

    return jsonify({
        'data': [serialize_review(r) for r in result['data']],
        'meta': result['meta']
    }), 200


@api.route('/professionals/<id>/reviews', methods=['POST'])
@token_required
def submit_review(current_user, id):
    professional = Professional.query.get(id)
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional not found'}), 404

    if professional.user_id == current_user.id:
        return jsonify({'code': 'FORBIDDEN', 'message': 'Cannot review yourself'}), 403

    data = request.get_json()
    if not data or 'rating' not in data or 'comment' not in data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'rating and comment are required'}), 400

    rating = data.get('rating')
    comment = data.get('comment')

    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'rating must be between 1 and 5'}), 400

    if not isinstance(comment, str) or len(comment) < 1 or len(comment) > 2000:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'comment must be between 1 and 2000 characters'}), 400

    existing_review = Review.query.filter_by(professional_id=id, user_id=current_user.id).first()
    if existing_review:
        existing_review.rating = rating
        existing_review.comment = comment
        db.session.commit()
        review = existing_review
    else:
        review = Review(
            id=generate_uuid(),
            professional_id=id,
            user_id=current_user.id,
            user_name=current_user.name,
            user_avatar_url=current_user.avatar_url,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()

        all_reviews = Review.query.filter_by(professional_id=id).all()
        avg_rating = sum(r.rating for r in all_reviews) / len(all_reviews)
        professional.rating = round(avg_rating, 2)
        professional.reviews_count = len(all_reviews)
        db.session.commit()

    return jsonify(serialize_review(review)), 201


@api.route('/professionals/<id>', methods=['PUT'])
@token_required
def update_professional(current_user, id):
    professional = Professional.query.get(id)
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional not found'}), 404

    if professional.user_id != current_user.id:
        return jsonify({'code': 'FORBIDDEN', 'message': 'You can only update your own profile'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'Request body is required'}), 400

    if 'title' in data:
        professional.title = data['title']
    if 'description' in data:
        professional.description = data['description']
    if 'phone' in data:
        professional.phone = data['phone']
    if 'instagram' in data:
        professional.instagram = data['instagram']
    if 'website' in data:
        professional.website = data['website']
    if 'registrationNumber' in data:
        professional.registration_number = data['registrationNumber']

    if 'categories' in data:
        category_slugs = data['categories']
        categories = Category.query.filter(Category.slug.in_(category_slugs)).all()
        professional.categories = categories

    db.session.commit()

    return jsonify(serialize_professional(professional, include_full=True)), 200


@api.route('/professionals/<id>/availability', methods=['PUT'])
@token_required
def toggle_availability(current_user, id):
    professional = Professional.query.get(id)
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional not found'}), 404

    if professional.user_id != current_user.id:
        return jsonify({'code': 'FORBIDDEN', 'message': 'You can only update your own availability'}), 403

    data = request.get_json()
    if not data or 'available' not in data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'available field is required'}), 400

    professional.available = data['available']
    db.session.commit()

    return jsonify({'message': 'Availability updated'}), 200


@api.route('/professionals/me', methods=['GET'])
@token_required
def get_my_professional_profile(current_user):
    if current_user.role != 'professional':
        return jsonify({'code': 'NOT_FOUND', 'message': 'User is not a professional'}), 404

    professional = Professional.query.filter_by(user_id=current_user.id).first()
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional profile not found'}), 404

    return jsonify(serialize_professional(professional, include_full=True)), 200


@api.route('/professionals/me', methods=['PUT'])
@token_required
def update_my_professional_profile(current_user):
    if current_user.role != 'professional':
        return jsonify({'code': 'NOT_FOUND', 'message': 'User is not a professional'}), 404

    professional = Professional.query.filter_by(user_id=current_user.id).first()
    if not professional:
        return jsonify({'code': 'NOT_FOUND', 'message': 'Professional profile not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'Request body is required'}), 400

    if 'title' in data:
        professional.title = data['title']
    if 'description' in data:
        professional.description = data['description']
    if 'phone' in data:
        professional.phone = data['phone']
    if 'instagram' in data:
        professional.instagram = data['instagram']
    if 'website' in data:
        professional.website = data['website']
    if 'registrationNumber' in data:
        professional.registration_number = data['registrationNumber']

    if 'categories' in data:
        category_slugs = data['categories']
        categories = Category.query.filter(Category.slug.in_(category_slugs)).all()
        professional.categories = categories

    db.session.commit()

    return jsonify(serialize_professional(professional, include_full=True)), 200


@api.route('/professionals', methods=['GET'])
def search_professionals():
    q = request.args.get('q', '')
    category = request.args.get('category')
    state = request.args.get('state')
    city = request.args.get('city')
    min_rating = request.args.get('rating', type=float)
    sort = request.args.get('sort', 'relevance')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    query = Professional.query.filter_by(available=True)

    if q:
        search_term = f'%{q}%'
        query = query.filter(
            db.or_(
                Professional.name.ilike(search_term),
                Professional.title.ilike(search_term),
                Professional.description.ilike(search_term)
            )
        )

    if category:
        query = query.filter(Professional.categories.any(Category.slug == category))

    if state:
        query = query.filter(Professional.state.ilike(state))

    if city:
        query = query.filter(Professional.city.ilike(city))

    if min_rating is not None:
        query = query.filter(Professional.rating >= min_rating)

    if sort == 'rating':
        query = query.order_by(Professional.rating.desc())
    elif sort == 'newest':
        query = query.order_by(Professional.created_at.desc())
    elif sort == 'reviews_count':
        query = query.order_by(Professional.reviews_count.desc())
    elif sort == 'featured':
        query = query.order_by(Professional.featured.desc(), Professional.rating.desc())
    else:
        query = query.order_by(Professional.rating.desc(), Professional.reviews_count.desc())

    result = paginate_query(query, page, limit)

    return jsonify({
        'data': [serialize_professional(p) for p in result['data']],
        'meta': result['meta']
    }), 200


@api.route('/users/me', methods=['GET'])
@token_required
def get_my_profile(current_user):
    return jsonify(serialize_user(current_user)), 200


@api.route('/users/me', methods=['PUT'])
@token_required
def update_my_profile(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'code': 'INVALID_REQUEST', 'message': 'Request body is required'}), 400

    if 'name' in data:
        current_user.name = data['name']
    if 'phone' in data:
        current_user.phone = data['phone']
    if 'avatarUrl' in data:
        current_user.avatar_url = data['avatarUrl']

    if 'address' in data and data['address']:
        addr = data['address']
        if 'state' in addr:
            current_user.address_state = addr['state']
        if 'city' in addr:
            current_user.address_city = addr['city']
        if 'district' in addr:
            current_user.address_district = addr['district']
        if 'street' in addr:
            current_user.address_street = addr['street']
        if 'number' in addr:
            current_user.address_number = addr['number']

    db.session.commit()

    return jsonify(serialize_user(current_user)), 200
