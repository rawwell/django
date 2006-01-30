"""
4. Many-to-one relationships

To define a many-to-one relationship, use ``ForeignKey()`` .
"""

from django.db import models

class Reporter(models.Model):
    first_name = models.CharField(maxlength=30)
    last_name = models.CharField(maxlength=30)
    email = models.EmailField()

    def __repr__(self):
        return "%s %s" % (self.first_name, self.last_name)

class Article(models.Model):
    headline = models.CharField(maxlength=100)
    pub_date = models.DateField()
    reporter = models.ForeignKey(Reporter)

    def __repr__(self):
        return self.headline


API_TESTS = """
# Create a few Reporters.
>>> r = Reporter(first_name='John', last_name='Smith', email='john@example.com')
>>> r.save()

>>> r2 = Reporter(first_name='Paul', last_name='Jones', email='paul@example.com')
>>> r2.save()

# Create an Article.
>>> from datetime import datetime
>>> a = Article(id=None, headline="This is a test", pub_date=datetime(2005, 7, 27), reporter=r)
>>> a.save()

>>> a.reporter.id
1

>>> a.reporter
John Smith

# Article objects have access to their related Reporter objects.
>>> r = a.reporter
>>> r.first_name, r.last_name
('John', 'Smith')

# Create an Article via the Reporter object.
>>> new_article = r.article_set.add(headline="John's second story", pub_date=datetime(2005, 7, 29))
>>> new_article
John's second story
>>> new_article.reporter.id
1

>>> new_article2 = r2.article_set.add(headline="Paul's story", pub_date=datetime(2006, 1, 17))
>>> new_article2.reporter.id
2

# Reporter objects have access to their related Article objects.
>>> list(r.article_set.order_by('pub_date'))
[This is a test, John's second story]

>>> list(r.article_set.filter(headline__startswith='This'))
This is a test

>>> r.article_set.count()
2

>>> r2.article_set.count()
1

# Get articles by id
>>> list(Article.objects.filter(id__exact=1))
[This is a test]
>>> list(Article.objects.filter(pk=1))
[This is a test]

# Query on an article property
>>> list(Article.objects.filter(headline__startswith='This'))
[This is a test]

# The API automatically follows relationships as far as you need.
# Use double underscores to separate relationships.
# This works as many levels deep as you want. There's no limit.
# Find all Articles for any Reporter whose first name is "John".
>>> list(Article.objects.filter(reporter__first_name__exact='John').order_by('pub_date'))
[This is a test, John's second story]

# Query twice over the related field.
>>> list(Article.objects.filter(reporter__first_name__exact='John', reporter__last_name__exact='Smith'))
[This is a test, John's second story]

# The underlying query only makes one join when a related table is referenced twice.
>>> null, sql, null = Article.objects._get_sql_clause(True, reporter__first_name__exact='John', reporter__last_name__exact='Smith')
>>> sql.count('INNER JOIN')
1

# The automatically joined table has a predictable name.
>>> list(Article.objects.filter(reporter__first_name__exact='John').extra(where=["many_to_one_article__reporter.last_name='Smith'"]))
[This is a test, John's second story]

# Find all Articles for the Reporter whose ID is 1.
>>> list(Article.objects.filter(reporter__id__exact=1).order_by('pub_date'))
[This is a test, John's second story]
>>> list(Article.objects.filter(reporter__pk=1).order_by('pub_date'))
[This is a test, John's second story]

# You need two underscores between "reporter" and "id" -- not one.
>>> list(Article.objects.filter(reporter_id__exact=1))
Traceback (most recent call last):
    ...
TypeError: Cannot resolve keyword 'reporter_id' into field

# You need to specify a comparison clause
>>> list(Article.objects.filter(reporter_id=1))
Traceback (most recent call last):
    ...
TypeError: Cannot parse keyword query 'reporter_id'

# "pk" shortcut syntax works in a related context, too.
>>> list(Article.objects.filter(reporter__pk=1).order_by('pub_date'))
[This is a test, John's second story]

# You can also instantiate an Article by passing
# the Reporter's ID instead of a Reporter object.
>>> a3 = Article(id=None, headline="This is a test", pub_date=datetime(2005, 7, 27), reporter_id=r.id)
>>> a3.save()
>>> a3.reporter.id
1
>>> a3.reporter
John Smith

# Similarly, the reporter ID can be a string.
>>> a4 = Article(id=None, headline="This is a test", pub_date=datetime(2005, 7, 27), reporter_id="1")
>>> a4.save()
>>> a4.reporter
John Smith

# Reporters can be queried
>>> list(Reporter.objects.filter(id__exact=1))
[John Smith]
>>> list(Reporter.objects.filter(pk=1))
[John Smith]
>>> list(Reporter.objects.filter(first_name__startswith='John'))
[John Smith]

# Reporters can query in opposite direction of ForeignKey definition
>>> list(Reporter.objects.filter(article__id__exact=1))
[John Smith]
>>> list(Reporter.objects.filter(article__pk=1))
[John Smith]
>>> list(Reporter.objects.filter(article__headline__startswith='This'))
[John Smith, John Smith, John Smith]
>>> list(Reporter.objects.filter(article__headline__startswith='This', distinct=True))
[John Smith]

# Queries can go round in circles.
>>> list(Reporter.objects.filter(article__reporter__first_name__startswith='John'))
[John Smith, John Smith, John Smith, John Smith]
>>> list(Reporter.objects.filter(article__reporter__first_name__startswith='John', distinct=True))
[John Smith]

# Deletes that require joins are prohibited.
>>> Article.objects.delete(reporter__first_name__startswith='Jo')
Traceback (most recent call last):
    ...
TypeError: Joins are not allowed in this type of query

# If you delete a reporter, his articles will be deleted.
>>> list(Article.objects.order_by('headline'))
[John's second story, Paul's story, This is a test, This is a test, This is a test]
>>> list(Reporter.objects.order_by('first_name'))
[John Smith, Paul Jones]
>>> r.delete()
>>> list(Article.objects.order_by('headline'))
[Paul's story]
>>> list(Reporter.objects.order_by('first_name'))
[Paul Jones]

"""
