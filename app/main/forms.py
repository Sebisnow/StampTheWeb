from flask_wtf import Form
from wtforms import StringField, TextAreaField, BooleanField, SelectField, \
    SubmitField, RadioField
from wtforms.validators import Length, Email, Regexp, DataRequired
from wtforms import ValidationError, validators
from flask_pagedown.fields import PageDownField
from flask_wtf.file import FileField
from ..models import Role, User
from wtforms.fields.html5 import URLField, IntegerField, EmailField
from wtforms.validators import url


class NameForm(Form):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')


class EditProfileForm(Form):
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')


class EditProfileAdminForm(Form):
    email = StringField('Email', validators=[DataRequired(), Length(1, 64),
                                             Email()], render_kw={"placeholder": "email@example.com"})
    username = StringField('Username', validators=[
        DataRequired(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                              'Usernames must have letters only, '
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
    body = TextAreaField("Add a Title (Optional) <i class='glyphicon glyphicon-info-sign'></i>",
                         render_kw={"title": "Titles help other users more quickly identify news articles."})
    urlSite = URLField("Enter URL to create its timestamp <i class='glyphicon glyphicon-asterisk'></i>", validators=[url(), DataRequired()],
                       render_kw={"placeholder": "http://www.example.com"})
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})


class PostEdit(Form):
    body = TextAreaField("Edit the title <i class='glyphicon glyphicon-info-sign'></i>",
                         render_kw={"title": "Titles help other users more quickly identify news articles."})
    submit = SubmitField('Update', render_kw={"onclick": "loading()"})


class PostFreq(Form):
    body = TextAreaField("Add a Title (Optional) <i class='glyphicon glyphicon-info-sign'></i>",
                         render_kw={"title": "Titles help other users more quickly identify news articles."})
    url = URLField("Enter URL to be regularly timestamped <i class='glyphicon glyphicon-asterisk'></i>", validators=[url(), DataRequired()],
                   render_kw={"placeholder": "http://www.example.com"})
    frequency = IntegerField("The frequency (in days) for which timestamps should be created "
                             "<i class='glyphicon glyphicon-asterisk'></i>",
                             [DataRequired('num required.'),
                              validators.NumberRange(min=1, max=30)], default=3)
    email = EmailField("Notify me in case there is any change in content. (email required) "
                       "<i class='glyphicon glyphicon-info-sign'></i>",
                       render_kw={"placeholder": "email@example.com"})
    submit = SubmitField("Submit", render_kw={"onclick": "loading()"})


class PostCountry(Form):
    body = TextAreaField("Add a Title (Optional) <i class='glyphicon glyphicon-info-sign'></i>",
                         render_kw={"title": "Titles help other users more quickly identify news articles."})
    urlSite = URLField("Enter URL to be regularly timestamped <i class='glyphicon glyphicon-asterisk'></i>", validators=[url(), DataRequired()],
                       render_kw={"placeholder": "http://www.example.com"})
    frequency = IntegerField("The frequency (in days) for which timestamps should be created "
                             "<i class='glyphicon glyphicon-asterisk'></i>",
                             [DataRequired('num required.'),
                              validators.NumberRange(min=1, max=30)], default=3)
    choice_switcher = RadioField(
        "Country? <i class='glyphicon glyphicon-info-sign'></i>",
        [DataRequired()],
        choices=[('default', 'Compare with the Default location'),
                 ('china', 'Compare with the page in China'),
                 ('usa', 'Compare with the page in USA'),
                 ('uk', 'Compare with the page in UK'),
                 ('russia', 'Compare with the page in Russia')], default='default'
    )
    email = EmailField("Notify me in case there is any change in content. (email) "
                       "<i class='glyphicon glyphicon-info-sign'></i>",
                       render_kw={"placeholder": "email@example.com"})
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})


class PostBlock(Form):
    body = TextAreaField("Add a Title (Optional) <i class='glyphicon glyphicon-info-sign'></i>",
                         render_kw={"title": "Titles help other users to more quickly identify news articles."})
    urlSite = URLField("Enter URL to check if it is blocked <i class='glyphicon glyphicon-asterisk'></i>", validators=[url(), DataRequired()],
                       render_kw={"placeholder": "http://www.example.com"})
    choice_switcher = RadioField(
        "Country? <i class='glyphicon glyphicon-info-sign'></i>",
        [DataRequired()],
        choices=[('china', 'Check if it is Blocked in China'),
                 ('usa', 'Check if it is Blocked in USA'),
                 ('uk', 'Check if it is Blocked in UK'),
                 ('russia', 'Check if it is Blocked in Russia')], default='china'
    )
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})


class FormSubmit(Form):
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})


class PostVerify(Form):
    urlSite = StringField("Search by URL or text <i class='glyphicon glyphicon-asterisk'></i>", validators=[DataRequired()], render_kw={"placeholder": "search"})
    submit = SubmitField('Search', render_kw={"onclick": "loading()", "title": "some Title"})


class SearchPost(Form):
    urlSite = StringField("", validators=[DataRequired()], render_kw={"placeholder": "Search"})
    submit = SubmitField('Search', render_kw={"onclick": "loading()"})


class URL_Status(Form):
    urlSite = URLField("Enter URL to check where it is blocked? <i class='glyphicon glyphicon-asterisk'></i>",
                       validators=[url(), DataRequired()],
                       render_kw={"placeholder": "http://www.example.com"},)
    submit = SubmitField('Search', render_kw={"onclick": "loading()"})


class SearchOptions(Form):
    choice_switcher = RadioField(
        'Country?',
        [DataRequired()],
        choices=[('china', 'Compare with same page in China'),
                 ('usa', 'Compare with same page in USA'),
                 ('uk', 'Compare with same page in UK'),
                 ('russia', 'Compare with same page in Russia')], default='china'
    )
    submit = SubmitField('Compare', render_kw={"onclick": "loading()"})


class PostHash(Form):
    hashValue = PageDownField("Enter Hash to create a timestamp", validators=[DataRequired()])
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})


class UploadFile(Form):
    fileName = FileField('Upload a file to Timestamp')


class PostText(Form):
    body = PageDownField("Enter Text to create its Timestamp?", validators=[DataRequired()])
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})


class Regular_Interval(Form):
    urlSite = URLField("Enter URL to create a timestamp", validators=[url()])
    submit = SubmitField('Submit', render_kw={"onclick": "loading()"})
