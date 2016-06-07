from flask.ext.wtf import Form
from wtforms import StringField, TextAreaField, BooleanField, SelectField,\
    SubmitField,RadioField
from wtforms.validators import Required, Length, Email, Regexp
from wtforms import ValidationError,validators
from flask.ext.pagedown.fields import PageDownField
from flask_wtf.file import FileField
from ..models import Role, User
from wtforms.fields.html5 import URLField,IntegerField,EmailField
from wtforms.validators import url


class NameForm(Form):
    name = StringField('What is your name?', validators=[Required()])
    submit = SubmitField('Submit')


class EditProfileForm(Form):
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')


class EditProfileAdminForm(Form):
    email = StringField('Email', validators=[Required(), Length(1, 64),
                                             Email()])
    username = StringField('Username', validators=[
        Required(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                          'Usernames must have only letters, '
                                          'numbers, dots or underscores')])
    confirmed = BooleanField('Confirmed')
    role = SelectField('Role', coerce=int)
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name)
                             for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and \
                User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if field.data != self.user.username and \
                User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already in use.')


class PostForm(Form):
    body = TextAreaField("Add a Title", validators=[Required()])
    urlSite = URLField("Enter URL to create a timestamp",validators=[url()])
    submit = SubmitField('Submit')

class PostFreq(Form):
    body = TextAreaField("Add a Title", validators=[Required()])
    urlSite = URLField("Enter URL to create a timestamp",validators=[url()])
    frequency = IntegerField('The frequency (in days) at which the stamps are created?', [validators.DataRequired('num required.'), validators.NumberRange(min=1, max=30)])
    email = EmailField('Email! if notification if required in case of content changes')
    china = BooleanField('Compare with same page in China')
    usa = BooleanField('Compare with same page in USA')
    uk = BooleanField('Compare with same page in UK')
    submit = SubmitField('Submit')

class FormSubmit(Form):
    submit = SubmitField('Submit')

class PostVerify(Form):
    urlSite = TextAreaField("Search by URL or text",validators=[Required()])
    submit = SubmitField('Submit')

class SearchPost(Form):
    urlSite = TextAreaField("Search Post",validators=[Required()])
    submit = SubmitField('Search')

class SearchOptions(Form):
    #china = RadioField('', choices=[('china','China')])
    #usa = RadioField('', choices=[('usa','USA')])
    #uk = RadioField('', choices=[('uk','UK')])
    china = BooleanField('Compare with same page in China')
    usa = BooleanField('Compare with same page in USA')
    uk = BooleanField('Compare with same page in UK')
    submit = SubmitField('Compare')

class PostHash(Form):
    hashValue = PageDownField("Enter Hash to create a timestamp",validators=[Required()])
    submit = SubmitField('Submit')

class UploadFile(Form):
    fileName = FileField('Upload a file to Timestamp')

class PostText(Form):
    body = PageDownField("Enter Text to create its Timestamp?", validators=[Required()])
    submit = SubmitField('Submit')

class Regular_Interval(Form):
    urlSite = URLField("Enter URL to create a timestamp",validators=[url()])
    submit = SubmitField('Submit')

