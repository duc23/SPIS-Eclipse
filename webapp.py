from flask import Flask, redirect, url_for, session, request, jsonify
from flask_oauthlib.client import OAuth
from flask import render_template, flash, Markup
from flask_pymongo import PyMongo
from github import Github

import pprint
import os
import sys
import traceback

class GithubOAuthVarsNotDefined(Exception):
    '''raise this if the necessary env variables are not defined '''

if os.getenv('GITHUB_CLIENT_ID') == None or \
        os.getenv('GITHUB_CLIENT_SECRET') == None or \
        os.getenv('APP_SECRET_KEY') == None or \
        os.getenv('GITHUB_ORG') == None:
    raise GithubOAuthVarsNotDefined('''
      Please define environment variables:
         GITHUB_CLIENT_ID
         GITHUB_CLIENT_SECRET
         GITHUB_ORG
         APP_SECRET_KEY
      ''')

app = Flask(__name__)

app.debug = False

app.secret_key = os.environ['APP_SECRET_KEY']
oauth = OAuth(app)

github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'],
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],
    request_token_params={'scope': 'read:org'},
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize'
)

app.config['MONGO_HOST'] = os.environ['MONGO_HOST']
app.config['MONGO_PORT'] = int(os.environ['MONGO_PORT'])
app.config['MONGO_DBNAME'] = os.environ['MONGO_DBNAME']
app.config['MONGO_USERNAME'] = os.environ['MONGO_USERNAME']
app.config['MONGO_PASSWORD'] = os.environ['MONGO_PASSWORD']
mongo = PyMongo(app)

@github.tokengetter
def get_github_oauth_token():
    return session.get('github_token')

@app.context_processor
def inject_logged_in():
    return dict(logged_in=('github_token' in session))

@app.context_processor
def inject_github_org():
    return dict(github_org=os.getenv('GITHUB_ORG'))

@app.route('/login')
def login():
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='https'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out')
    return redirect(url_for('home'))

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()

    if resp is None:
        session.clear()
        login_error_message = 'Access denied: reason=%s error=%s full=%s' % (
            request.args['error'],
            request.args['error_description'],
            pprint.pformat(request.args)
        )        
        flash(login_error_message, 'error')
        return redirect(url_for('home'))    

    try:
        session['github_token'] = (resp['access_token'], '')
        session['user_data']=github.get('user').data
        github_userid = session['user_data']['login']
        org_name = os.getenv('GITHUB_ORG')
    except Exception as e:
        session.clear()
        message = 'Unable to login: ' + str(type(e)) + str(e)
        flash(message,'error')
        return redirect(url_for('home'))
    
    try:
        g = Github(resp['access_token'])
        org = g.get_organization(org_name)
        named_user = g.get_user(github_userid)
        isMember = org.has_in_members(named_user)
    except Exception as e:
        message = 'Unable to connect to Github with accessToken: ' + resp['access_token'] + " exception info: " + str(type(e)) + str(e)
        session.clear()
        flash(message,'error')
        return redirect(url_for('home'))
    
    if not isMember:
        session.clear() # Must clear session before adding flash message
        message = 'Unable to login: ' + github_userid + ' is not a member of ' + org_name + \
          '</p><p><a href="https://github.com/logout" target="_blank">Logout of github as user:  ' + github_userid + \
          '</a></p>' 
        flash(Markup(message),'error')

    else:
        flash('You were successfully logged in')

    return redirect(url_for('home'))

@app.route('/home')
@app.route('/')
def home():
    if 'user_data' in session:
        user_data_pprint = pprint.pformat(session['user_data'])
    else:
        user_data_pprint = '';
    return render_template('home.html',dump_user_data=user_data_pprint)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/locations')
def locations():
    return render_template('locations.html')


@app.route('/result')
def result():
    var=request.args['location']
    if var == "unitedstates":
        return redirect(url_for('unitedstates'))
    elif var == "mexico":
        return redirect(url_for('mexico'))
    elif var == "canada":
        return redirect(url_for('canada'))

@app.route('/unitedstates')
def unitedstates():
    return render_template('unitedstates.html')

@app.route('/mexico')
def mexico():
    return render_template('mexico.html')

@app.route('/canada')
def canada():
    return render_template('canada.html')

@app.route('/news')
def news():
    return render_template('news.html')


@app.route('/email_result')
def email_result():
    user_email = request.args["email"]
    mongo.db.eclipsenews.insert_one( {"email" : user_email })
    return redirect(url_for('finish'))

@app.route('/finish')
def finish():
    return render_template('finish.html')




if __name__ == "__main__":
    app.run(port=5000,debug=False)
