from flask import Flask, render_template, request, redirect, make_response
from flask import url_for, flash, jsonify, Response, session as login_session
from models import Base, Checkpoint, User, Token
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.inspection import inspect
from sqlalchemy import create_engine
import random
import string
from authlib.flask.client import OAuth
from six.moves.urllib.parse import urlencode
from functools import wraps
import os.path

engine = create_engine('postgresql://'+os.getenv('user') +
                       ':'+os.getenv('password')+'@localhost:5432/bestplaces')

Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

app = Flask(__name__)

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id='yhuJDot9gC0quQQeVBmliVO6awv2GExd',
    client_secret='xbhnxFiMBhRn4FM6cw6l3gH80VYN5M' +
    'bTyW0RbL5PfOPqD0eFUuUOi8aff8Dn7SKh',
    api_base_url='https://fadingminotaur5.auth0.com',
    access_token_url='https://fadingminotaur5.auth0.com/oauth/token',
    authorize_url='https://fadingminotaur5.auth0.com/authorize',
    client_kwargs={
        'scope': 'openid profile email',
    },
)

# Auth Controllers


def userLoggedIn():
    if 'profile' in login_session:
        return True
    else:
        return False


app.jinja_env.globals.update(userLoggedIn=userLoggedIn)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'profile' not in login_session:
            # Redirect to Login page here
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def requires_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        access_token = request.headers.get('access_token')

        if not access_token:
            return make_response(
                jsonify(
                    status=403,
                    result= {
                        'message': 'No access token provided!'
                    }
                ), 403
            )
        
        try:
            token = session.query(Token).filter_by(token=access_token).one()
            
        except Exception:
            return make_response(
                jsonify(
                    status=403,
                    result= {
                        'message': 'Unauthorized access token!'
                    }
                ), 403
            )

        return f(*args, **kwargs)
    return decorated


@app.route('/callback')
def callback_handling():
    # Handles response from token endpoint
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    # Store the user information in flask session.
    login_session['jwt_payload'] = userinfo

    user_id = getUserId(userinfo['email'])

    if user_id is None:
        user_id = createUser(userinfo)

    login_session['profile'] = {
        'user_id': user_id,
        'name': userinfo['name'],
        'email': userinfo['email'],
        'picture': userinfo['picture']
    }

    app.jinja_env.globals.update(user=login_session['profile'])

    return redirect('/')


@app.route('/connect')
def login():
    return auth0.authorize_redirect(
        redirect_uri='http://localhost:5000/callback',
        audience='https://fadingminotaur5.auth0.com/userinfo'
    )

@app.route('/generate_new_token')
def generate_token():

    token = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))

    insertToken = Token(
        name='first_token',
        token=token
    )

    session.add(insertToken)
    session.commit()
    
    try:
        newToken = session.query(Token).filter_by(token=token).one()
        return make_response(
            jsonify(
                status=200,
                result = {
                    'token': newToken.token
                }
            ), 200
        )
    except Exception:
        return make_response(
            jsonify(
                status=500,
                result = {
                    'message': 'Something went wrong'
                }
            ), 500
        )
        
    


@app.route('/logout')
def logout():
    # Clear session stored data
    login_session.clear()
    app.jinja_env.globals.update(user=False)
    # Redirect user to logout endpoint
    params = {
        'returnTo': url_for(
            'index', _external=True
        ),
        'client_id': 'GHFAORqpG5uLMAqqBPF1w4DxhUlaaBFq'
    }
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))


@app.route('/unauthorized')
def unauthorize():
    return render_template('auth/unauthorized.html')


# User Controllers
def createUser(userInfo):
    newUser = User(
        name=userInfo['name'],
        email=userInfo['email'],
        picture=userInfo['picture']
    )

    session.add(newUser)
    session.commit()

    user = session.query(User).filter_by(email=userInfo['email']).one()
    return user.id


def getUser(id):
    user = session.query(User).filter_by(id=id).one()
    return user


def getUserId(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Categories Controllers
@app.route('/categories/json')
def viewCategoriesJson():
    categories = session.query(Category).all()

    return jsonify(
        status=200,
        result=[
            category.serialize for category in categories
        ]
    )


@app.route('/')
@requires_token
def index():
    checkpoints = session.query(Checkpoint).all()
    if 'profile' in login_session:
        user = login_session['profile']
    else:
        user = False

    return make_response(
        jsonify(
            status=200,
            result = {
                'checkpoint': [checkpoint.serialize for checkpoint in checkpoints],
                'user': user
            }
        ), 200
    )


@app.route('/category/<int:category_id>/')
def viewCategory(category_id):
    if category_id:
        category = session.query(Category).filter_by(id=category_id).one()
        items = session.query(Item).filter_by(category_id=category_id)
    return render_template(
        'category/view.html',
        category=category,
        items=items
    )


@app.route('/category/create', methods=['GET', 'POST'])
@requires_auth
def createCategory():
    if request.method == 'GET':
        return render_template('category/create.html')
    else:
        newEntry = Category(
            name=request.form['name'],
            user_id=login_session['profile']['user_id']
        )
        session.add(newEntry)
        session.commit()
        return redirect(url_for('index'))


@app.route('/category/update/<int:category_id>', methods=['GET', 'POST'])
@requires_auth
def updateCategory(category_id):
    if not isCategoryOwner(category_id):
        return redirect(url_for('unauthorize'))

    category = session.query(Category).filter_by(id=category_id).one()

    if request.method == 'GET':

        return render_template('category/update.html', category=category)
    else:
        category.name = request.form['name']
        session.add(category)
        session.commit()
        return redirect(url_for('index'))


@app.route('/category/delete/<int:category_id>', methods=['GET', 'POST'])
@requires_auth
def deleteCategory(category_id):
    if not isCategoryOwner(category_id):
        return redirect(url_for('unauthorize'))

    category = session.query(Category).filter_by(id=category_id).one()

    if request.method == 'GET':

        return render_template('category/delete.html', category=category)
    else:
        session.delete(category)
        session.commit()
        return redirect(url_for('index'))


def isCategoryOwner(category_id):
    category = session.query(Category).filter_by(id=category_id).one()

    if not userLoggedIn():
        return False

    if login_session['profile']['user_id'] == category.user_id:
        return True
    else:
        return False


app.jinja_env.globals.update(isCategoryOwner=isCategoryOwner)


# Items Controllers
@app.route('/item/<int:category_id>/json')
def viewItemsJson(category_id):
    items = session.query(Item).filter_by(category_id=category_id)

    return jsonify(status=200, result=[item.serialize for item in items])


@app.route('/item/<int:item_id>/')
def viewItem(item_id):
    if item_id:
        item = session.query(Item).filter_by(id=item_id).one()
    return render_template('item/view.html', item=item)


@app.route('/item/create/<int:category_id>', methods=['GET', 'POST'])
@requires_auth
def createItem(category_id):
    if not isCategoryOwner(category_id):
        return redirect(url_for('unauthorize'))

    if request.method == 'GET':
        category = session.query(Category).filter_by(id=category_id).one()
        return render_template('item/create.html', category=category)
    else:
        newEntry = Item(
            name=request.form['name'],
            description=request.form['description'],
            category_id=category_id,
            user_id=login_session['profile']['user_id']
        )
        session.add(newEntry)
        session.commit()
        return redirect(url_for('viewCategory', category_id=category_id))


@app.route('/item/update/<int:item_id>', methods=['GET', 'POST'])
@requires_auth
def updateItem(item_id):
    if not isItemOwner(item_id):
        return redirect(url_for('unauthorize'))

    item = session.query(Item).filter_by(id=item_id).one()

    if request.method == 'GET':

        return render_template('item/update.html', item=item)
    else:
        item.name = request.form['name']
        item.description = request.form['description']
        session.add(item)
        session.commit()
        return redirect(url_for('viewCategory', category_id=item.category_id))


@app.route('/item/delete/<int:item_id>', methods=['GET', 'POST'])
@requires_auth
def deleteItem(item_id):
    if not isItemOwner(item_id):
        return redirect(url_for('unauthorize'))

    item = session.query(Item).filter_by(id=item_id).one()
    if request.method == 'GET':

        return render_template('item/delete.html', item=item)
    else:
        session.delete(item)
        session.commit()
        return redirect(url_for('viewCategory', category_id=item.category_id))


def isItemOwner(item_id):
    item = session.query(Item).filter_by(id=item_id).one()

    if not userLoggedIn():
        return False

    if login_session['profile']['user_id'] == item.user_id:
        return True
    else:
        return False


app.jinja_env.globals.update(isItemOwner=isItemOwner)


if __name__ == '__main__':
    app.debug = True
    app.secret_key = 'UX4Z2NPLR37OIG8PREXCQUKPKA59HQXY'
    app.run(host='0.0.0.0', port=5000)
