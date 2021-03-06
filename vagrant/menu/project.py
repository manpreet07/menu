from functools import wraps
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem, User

from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash

app = Flask(__name__)

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant"

# Connect to Database and create database session
engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if 'username' not in login_session:
      return redirect(url_for('showLogin', next=request.url))
    return f(*args, **kwargs)

  return decorated_function


# Create anti-forgery state token
@app.route('/login')
def showLogin():
  state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                  for x in xrange(32))
  login_session['state'] = state
  return render_template('login.html', STATE=state)


@app.route('/')
def allCateories():
  """
  Method returns all categories and number of items for that category
  """
  menuItems = {}
  restaurants = session.query(Restaurant).order_by(asc(Restaurant.name))
  for restaurant in restaurants:
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant.id).all()
    if len(items):
      menuItems[restaurant] = len(items)
    else:
      menuItems[restaurant] = 0
  return render_template('home.html', menuItems=menuItems)


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
  if request.args.get('state') != login_session['state']:
    response = make_response(json.dumps('Invalid state parameter.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response
  access_token = request.data
  print "access token received %s " % access_token

  app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
    'web']['app_id']
  app_secret = json.loads(
    open('fb_client_secrets.json', 'r').read())['web']['app_secret']
  url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
    app_id, app_secret, access_token)
  h = httplib2.Http()
  result = h.request(url, 'GET')[1]

  # Use token to get user info from API
  userinfo_url = "https://graph.facebook.com/v2.4/me"
  # strip expire tag from access token
  token = result.split("&")[0]

  url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
  h = httplib2.Http()
  result = h.request(url, 'GET')[1]
  # print "url sent for API access:%s"% url
  # print "API JSON result: %s" % result
  data = json.loads(result)
  login_session['provider'] = 'facebook'
  login_session['username'] = data["name"]
  login_session['email'] = data["email"]
  login_session['facebook_id'] = data["id"]

  # The token must be stored in the login_session in order to properly logout, let's strip out the information before the equals sign in our token
  stored_token = token.split("=")[1]
  login_session['access_token'] = stored_token

  # Get user picture
  url = 'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' % token
  h = httplib2.Http()
  result = h.request(url, 'GET')[1]
  data = json.loads(result)

  login_session['picture'] = data["data"]["url"]

  # see if user exists
  user_id = getUserID(login_session['email'])
  if not user_id:
    user_id = createUser(login_session)
  login_session['user_id'] = user_id

  return "Welcome %s" % login_session['username']


@app.route('/gconnect', methods=['POST'])
def gconnect():
  # Validate state token
  if request.args.get('state') != login_session['state']:
    response = make_response(json.dumps('Invalid state parameter.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response
  # Obtain authorization code
  code = request.data

  try:
    # Upgrade the authorization code into a credentials object
    oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
    oauth_flow.redirect_uri = 'postmessage'
    credentials = oauth_flow.step2_exchange(code)

  except FlowExchangeError:
    response = make_response(
      json.dumps('Failed to upgrade the authorization code.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response

  # Check that the access token is valid.
  access_token = credentials.access_token
  url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
         % access_token)
  h = httplib2.Http()
  result = json.loads(h.request(url, 'GET')[1])
  # If there was an error in the access token info, abort.
  if result.get('error') is not None:
    response = make_response(json.dumps(result.get('error')), 500)
    response.headers['Content-Type'] = 'application/json'

  # Verify that the access token is used for the intended user.
  gplus_id = credentials.id_token['sub']
  if result['user_id'] != gplus_id:
    response = make_response(
      json.dumps("Token's user ID doesn't match given user ID."), 401)
    response.headers['Content-Type'] = 'application/json'
    return response

  # Verify that the access token is valid for this app.
  if result['issued_to'] != CLIENT_ID:
    response = make_response(
      json.dumps("Token's client ID does not match app's."), 401)
    print "Token's client ID does not match app's."
    response.headers['Content-Type'] = 'application/json'
    return response

  stored_credentials = login_session.get('credentials')
  stored_gplus_id = login_session.get('gplus_id')
  if stored_credentials is not None and gplus_id == stored_gplus_id:
    response = make_response(json.dumps('Current user is already connected.'),
                             200)
    response.headers['Content-Type'] = 'application/json'
    return response

  # Store the access token in the session for later use.
  login_session['credentials'] = credentials.to_json()
  login_session['gplus_id'] = gplus_id

  # Get user info
  userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
  params = {'access_token': credentials.access_token, 'alt': 'json'}
  answer = requests.get(userinfo_url, params=params)

  data = answer.json()

  login_session['provider'] = 'google'
  login_session['username'] = data['name']
  login_session['picture'] = data['picture']
  login_session['email'] = data['email']
  login_session['access_token'] = credentials.access_token

  userId = getUserID(login_session['email'])

  if userId is None:
    user_id = createUser(login_session)
    login_session['user_id'] = user_id
  else:
    login_session['user_id'] = userId

  return "Welcome " + login_session['username']


def createUser(login_session):
  newUser = User(name=login_session['username'], email=login_session[
    'email'], picture=login_session['picture'])
  session.add(newUser)
  session.commit()
  user = session.query(User).filter_by(email=login_session['email']).one()
  return user.id


def getUserInfo(user_id):
  user = session.query(User).filter_by(id=user_id).one()
  return user


def getUserID(email):
  try:
    user = session.query(User).filter_by(email=email).one()
    return user.id
  except:
    return None


@app.route('/disconnect')
def gdisconnect():
  if login_session['provider'] == "facebook":
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return redirect(url_for('showLogin'))

  if login_session['provider'] == "google":

    access_token = login_session['access_token']
    if access_token is None:
      print 'Access Token is None'
      response = make_response(json.dumps('Current user not connected.'), 401)
      response.headers['Content-Type'] = 'application/json'
      return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
      del login_session['access_token']
      del login_session['gplus_id']
      del login_session['username']
      del login_session['email']
      del login_session['picture']
      response = make_response(json.dumps('Successfully disconnected.'), 200)
      response.headers['Content-Type'] = 'application/json'
      return redirect(url_for('showLogin'))
    else:
      response = make_response(json.dumps('Failed to revoke token for given user.', 400))
      response.headers['Content-Type'] = 'application/json'
      return response


# JSON APIs to view Restaurant Information
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
  restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
  items = session.query(MenuItem).filter_by(restaurant_id=restaurant_id).all()
  return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
  Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
  return jsonify(Menu_Item=Menu_Item.serialize)


@app.route('/restaurant/JSON')
def restaurantsJSON():
  restaurants = session.query(Restaurant).all()
  return jsonify(restaurants=[r.serialize for r in restaurants])


# Show all restaurants

@app.route('/restaurant/')
@login_required
def showRestaurants():
    creator = getUserInfo(login_session['user_id'])
    restaurants = session.query(Restaurant).filter_by(user_id=creator.id).order_by(asc(Restaurant.name))
    return render_template('restaurants.html', restaurants=restaurants, login_session=login_session)


# Create a new restaurant
@app.route('/restaurant/new/', methods=['GET', 'POST'])
@login_required
def newRestaurant():
    if request.method == 'POST':
      if request.form['name']:
        newRestaurant = Restaurant(user_id=login_session['user_id'], name=request.form['name'])
        session.add(newRestaurant)
        flash('New Restaurant %s Successfully Created' % newRestaurant.name)
        session.commit()
        return redirect(url_for('showRestaurants'))
      else:
        return redirect(url_for('showRestaurants'))
    else:
      return render_template('newRestaurant.html', login_session=login_session)


# Edit a restaurant
@app.route('/restaurant/<int:restaurant_id>/edit/', methods=['GET', 'POST'])
@login_required
def editRestaurant(restaurant_id):
  editedRestaurant = session.query(Restaurant).filter_by(user_id=login_session['user_id'], id=restaurant_id).one()
  if request.method == 'POST':
    if request.form['name']:
      editedRestaurant.name = request.form['name']
      flash('Restaurant Successfully Edited %s' % editedRestaurant.name)
      return redirect(url_for('showRestaurants'))
  else:
    return render_template('editRestaurant.html', restaurant=editedRestaurant, login_session=login_session)


# Delete a restaurant
@app.route('/restaurant/<int:restaurant_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteRestaurant(restaurant_id):
  restaurantToDelete = session.query(Restaurant).filter_by(id=restaurant_id).one()
  if request.method == 'POST':
    session.delete(restaurantToDelete)
    flash('%s Successfully Deleted' % restaurantToDelete.name)
    session.commit()
    return redirect(url_for('showRestaurants', restaurant_id=restaurant_id))
  else:
    return render_template('deleteRestaurant.html', restaurant=restaurantToDelete, login_session=login_session)


# Show a restaurant menu
@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu/')
@login_required
def showMenu(restaurant_id):
  creator = getUserInfo(login_session['user_id'])
  restaurant = session.query(Restaurant).filter_by(user_id=login_session['user_id'], id=restaurant_id).one()
  items = session.query(MenuItem).filter_by(user_id=creator.id).all()
  return render_template('menu.html', items=items, restaurant=restaurant, login_session=login_session, creator=creator)


# Create a new menu item
@app.route('/restaurant/<int:restaurant_id>/menu/new/', methods=['GET', 'POST'])
@login_required
def newMenuItem(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(user_id=login_session['user_id'], id=restaurant_id).one()
    if request.method == 'POST':
      if request.form['name']:
        newItem = MenuItem(name=request.form['name'], description=request.form['description'],
                           price=request.form['price'], course=request.form['course'], restaurant_id=restaurant_id,
                           user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newItem.name))
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
      else:
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
      return render_template('newmenuitem.html', restaurant_id=restaurant_id, login_session=login_session)


# Edit a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit', methods=['GET', 'POST'])
@login_required
def editMenuItem(restaurant_id, menu_id):
    editedItem = session.query(MenuItem).filter_by(user_id=login_session['user_id'], id=menu_id).one()
    restaurant = session.query(Restaurant).filter_by(user_id=login_session['user_id'], id=restaurant_id).one()
    if request.method == 'POST':
      if request.form['name']:
        editedItem.name = request.form['name']
      if request.form['description']:
        editedItem.description = request.form['description']
      if request.form['price']:
        editedItem.price = request.form['price']
      if request.form['course']:
        editedItem.course = request.form['course']
      session.add(editedItem)
      session.commit()
      flash('Menu Item Successfully Edited')
      return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
      return render_template('editmenuitem.html', restaurant_id=restaurant_id, menu_id=menu_id, item=editedItem,
                             login_session=login_session)


# Delete a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteMenuItem(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(user_id=login_session['user_id'], id=restaurant_id).one()
    itemToDelete = session.query(MenuItem).filter_by(user_id=login_session['user_id'], id=menu_id).one()
    if request.method == 'POST':
      session.delete(itemToDelete)
      session.commit()
      flash('Menu Item Successfully Deleted')
      return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
      return render_template('deleteMenuItem.html', item=itemToDelete, login_session=login_session)


if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host='0.0.0.0', port=5000)
