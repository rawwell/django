
from django.core import mail
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm

class PasswordResetFormTestCase(TestCase):
    def testValidUser(self):
        data = {
            'email': 'nonexistent@example.com',
        }
        form = PasswordResetForm(data)
        self.assertEqual(form.is_valid(), False)
        self.assertEqual(form["email"].errors, [u"That e-mail address doesn't have an associated user account. Are you sure you've registered?"])
    
    def testEmail(self):
        # TODO: remove my email address from the test ;)
        User.objects.create_user('atestuser', 'atestuser@example.com', 'test789')
        data = {
            'email': 'atestuser@example.com',
        }
        form = PasswordResetForm(data)
        self.assertEqual(form.is_valid(), True)
        # TODO: look at why using contrib.sites breaks other tests
        form.save(domain_override="example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, u'Password reset on example.com')
        # TODO: test mail body. need to figure out a way to get the password in plain text
        # self.assertEqual(mail.outbox[0].body, '')

FORM_TESTS = """
>>> from django.contrib.auth.models import User
>>> from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
>>> from django.contrib.auth.forms import PasswordChangeForm

The user already exists.

>>> user = User.objects.create_user("jsmith", "jsmith@example.com", "test123")
>>> data = {
...     'username': 'jsmith',
...     'password1': 'test123',
...     'password2': 'test123',
... }
>>> form = UserCreationForm(data)
>>> form.is_valid()
False
>>> form["username"].errors
[u'A user with that username already exists.']

The username contains invalid data.

>>> data = {
...     'username': 'jsmith@example.com',
...     'password1': 'test123',
...     'password2': 'test123',
... }
>>> form = UserCreationForm(data)
>>> form.is_valid()
False
>>> form["username"].errors
[u'This value must contain only letters, numbers and underscores.']

The verification password is incorrect.

>>> data = {
...     'username': 'jsmith2',
...     'password1': 'test123',
...     'password2': 'test',
... }
>>> form = UserCreationForm(data)
>>> form.is_valid()
False
>>> form["password2"].errors
[u"The two password fields didn't match."]

The success case.

>>> data = {
...     'username': 'jsmith2',
...     'password1': 'test123',
...     'password2': 'test123',
... }
>>> form = UserCreationForm(data)
>>> form.is_valid()
True
>>> form.save()
<User: jsmith2>

The user submits an invalid username.

>>> data = {
...     'username': 'jsmith_does_not_exist',
...     'password': 'test123',
... }

>>> form = AuthenticationForm(None, data)
>>> form.is_valid()
False
>>> form.non_field_errors()
[u'Please enter a correct username and password. Note that both fields are case-sensitive.']

The user is inactive.

>>> data = {
...     'username': 'jsmith',
...     'password': 'test123',
... }
>>> user.is_active = False
>>> user.save()
>>> form = AuthenticationForm(None, data)
>>> form.is_valid()
False
>>> form.non_field_errors()
[u'This account is inactive.']

>>> user.is_active = True
>>> user.save()

The success case

>>> form = AuthenticationForm(None, data)
>>> form.is_valid()
True
>>> form.non_field_errors()
[]

The old password is incorrect.

>>> data = {
...     'old_password': 'test',
...     'new_password1': 'abc123',
...     'new_password2': 'abc123',
... }
>>> form = PasswordChangeForm(user, data)
>>> form.is_valid()
False
>>> form["old_password"].errors
[u'Your old password was entered incorrectly. Please enter it again.']

The two new passwords do not match.

>>> data = {
...     'old_password': 'test123',
...     'new_password1': 'abc123',
...     'new_password2': 'abc',
... }
>>> form = PasswordChangeForm(user, data)
>>> form.is_valid()
False
>>> form["new_password2"].errors
[u"The two password fields didn't match."]

The success case.

>>> data = {
...     'old_password': 'test123',
...     'new_password1': 'abc123',
...     'new_password2': 'abc123',
... }
>>> form = PasswordChangeForm(user, data)
>>> form.is_valid()
True

"""
