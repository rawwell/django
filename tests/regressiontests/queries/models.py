"""
Various complex queries that have been problematic in the past.
"""

import datetime

from django.db import models
from django.db.models.query import Q

class Tag(models.Model):
    name = models.CharField(max_length=10)
    parent = models.ForeignKey('self', blank=True, null=True)

    def __unicode__(self):
        return self.name

class Note(models.Model):
    note = models.CharField(max_length=100)
    misc = models.CharField(max_length=10)

    class Meta:
        ordering = ['note']

    def __unicode__(self):
        return self.note

class ExtraInfo(models.Model):
    info = models.CharField(max_length=100)
    note = models.ForeignKey(Note)

    class Meta:
        ordering = ['info']

    def __unicode__(self):
        return self.info

class Author(models.Model):
    name = models.CharField(max_length=10)
    num = models.IntegerField(unique=True)
    extra = models.ForeignKey(ExtraInfo)

    def __unicode__(self):
        return self.name

class Item(models.Model):
    name = models.CharField(max_length=10)
    created = models.DateTimeField()
    tags = models.ManyToManyField(Tag, blank=True, null=True)
    creator = models.ForeignKey(Author)
    note = models.ForeignKey(Note)

    class Meta:
        ordering = ['-note', 'name']

    def __unicode__(self):
        return self.name

class Report(models.Model):
    name = models.CharField(max_length=10)
    creator = models.ForeignKey(Author, to_field='num')

    def __unicode__(self):
        return self.name

class Ranking(models.Model):
    rank = models.IntegerField()
    author = models.ForeignKey(Author)

    class Meta:
        # A complex ordering specification. Should stress the system a bit.
        ordering = ('author__extra__note', 'author__name', 'rank')

    def __unicode__(self):
        return '%d: %s' % (self.rank, self.author.name)

class Cover(models.Model):
    title = models.CharField(max_length=50)
    item = models.ForeignKey(Item)

    class Meta:
        ordering = ['item']

    def __unicode__(self):
        return self.title

class Number(models.Model):
    num = models.IntegerField()

    def __unicode__(self):
        return unicode(self.num)

# Some funky cross-linked models for testing a couple of infinite recursion
# cases.
class X(models.Model):
    y = models.ForeignKey('Y')

class Y(models.Model):
    x1 = models.ForeignKey(X, related_name='y1')

# Some models with a cycle in the default ordering. This would be bad if we
# didn't catch the infinite loop.
class LoopX(models.Model):
    y = models.ForeignKey('LoopY')

    class Meta:
        ordering = ['y']

class LoopY(models.Model):
    x = models.ForeignKey(LoopX)

    class Meta:
        ordering = ['x']

class LoopZ(models.Model):
    z = models.ForeignKey('self')

    class Meta:
        ordering = ['z']

# A model and custom default manager combination.
class CustomManager(models.Manager):
    def get_query_set(self):
        return super(CustomManager, self).get_query_set().filter(public=True,
                tag__name='t1')

class ManagedModel(models.Model):
    data = models.CharField(max_length=10)
    tag = models.ForeignKey(Tag)
    public = models.BooleanField(default=True)

    objects = CustomManager()
    normal_manager = models.Manager()

    def __unicode__(self):
        return self.data


__test__ = {'API_TESTS':"""
>>> t1 = Tag(name='t1')
>>> t1.save()
>>> t2 = Tag(name='t2', parent=t1)
>>> t2.save()
>>> t3 = Tag(name='t3', parent=t1)
>>> t3.save()
>>> t4 = Tag(name='t4', parent=t3)
>>> t4.save()
>>> t5 = Tag(name='t5', parent=t3)
>>> t5.save()

>>> n1 = Note(note='n1', misc='foo')
>>> n1.save()
>>> n2 = Note(note='n2', misc='bar')
>>> n2.save()
>>> n3 = Note(note='n3', misc='foo')
>>> n3.save()

Create these out of order so that sorting by 'id' will be different to sorting
by 'info'. Helps detect some problems later.
>>> e2 = ExtraInfo(info='e2', note=n2)
>>> e2.save()
>>> e1 = ExtraInfo(info='e1', note=n1)
>>> e1.save()

>>> a1 = Author(name='a1', num=1001, extra=e1)
>>> a1.save()
>>> a2 = Author(name='a2', num=2002, extra=e1)
>>> a2.save()
>>> a3 = Author(name='a3', num=3003, extra=e2)
>>> a3.save()
>>> a4 = Author(name='a4', num=4004, extra=e2)
>>> a4.save()

>>> time1 = datetime.datetime(2007, 12, 19, 22, 25, 0)
>>> time2 = datetime.datetime(2007, 12, 19, 21, 0, 0)
>>> time3 = datetime.datetime(2007, 12, 20, 22, 25, 0)
>>> time4 = datetime.datetime(2007, 12, 20, 21, 0, 0)
>>> i1 = Item(name='one', created=time1, creator=a1, note=n3)
>>> i1.save()
>>> i1.tags = [t1, t2]
>>> i2 = Item(name='two', created=time2, creator=a2, note=n2)
>>> i2.save()
>>> i2.tags = [t1, t3]
>>> i3 = Item(name='three', created=time3, creator=a2, note=n3)
>>> i3.save()
>>> i4 = Item(name='four', created=time4, creator=a4, note=n3)
>>> i4.save()
>>> i4.tags = [t4]

>>> r1 = Report(name='r1', creator=a1)
>>> r1.save()
>>> r2 = Report(name='r2', creator=a3)
>>> r2.save()

Ordering by 'rank' gives us rank2, rank1, rank3. Ordering by the Meta.ordering
will be rank3, rank2, rank1.
>>> rank1 = Ranking(rank=2, author=a2)
>>> rank1.save()
>>> rank2 = Ranking(rank=1, author=a3)
>>> rank2.save()
>>> rank3 = Ranking(rank=3, author=a1)
>>> rank3.save()

>>> c1 = Cover(title="first", item=i4)
>>> c1.save()
>>> c2 = Cover(title="second", item=i2)
>>> c2.save()

>>> n1 = Number(num=4)
>>> n1.save()
>>> n2 = Number(num=8)
>>> n2.save()
>>> n3 = Number(num=12)
>>> n3.save()

Bug #1050
>>> Item.objects.filter(tags__isnull=True)
[<Item: three>]
>>> Item.objects.filter(tags__id__isnull=True)
[<Item: three>]

Bug #1801
>>> Author.objects.filter(item=i2)
[<Author: a2>]
>>> Author.objects.filter(item=i3)
[<Author: a2>]
>>> Author.objects.filter(item=i2) & Author.objects.filter(item=i3)
[<Author: a2>]

Bug #2306
Checking that no join types are "left outer" joins.
>>> query = Item.objects.filter(tags=t2).query
>>> query.LOUTER not in [x[2] for x in query.alias_map.values()]
True

>>> Item.objects.filter(Q(tags=t1)).order_by('name')
[<Item: one>, <Item: two>]
>>> Item.objects.filter(Q(tags=t1)).filter(Q(tags=t2))
[<Item: one>]
>>> Item.objects.filter(Q(tags=t1)).filter(Q(creator__name='fred')|Q(tags=t2))
[<Item: one>]

Each filter call is processed "at once" against a single table, so this is
different from the previous example as it tries to find tags that are two
things at once (rather than two tags).
>>> Item.objects.filter(Q(tags=t1) & Q(tags=t2))
[]
>>> Item.objects.filter(Q(tags=t1), Q(creator__name='fred')|Q(tags=t2))
[]

>>> qs = Author.objects.filter(ranking__rank=2, ranking__id=rank1.id)
>>> list(qs)
[<Author: a2>]
>>> qs.query.count_active_tables()
2
>>> qs = Author.objects.filter(ranking__rank=2).filter(ranking__id=rank1.id)
>>> qs.query.count_active_tables()
3

Bug #4464
>>> Item.objects.filter(tags=t1).filter(tags=t2)
[<Item: one>]
>>> Item.objects.filter(tags__in=[t1, t2]).distinct().order_by('name')
[<Item: one>, <Item: two>]
>>> Item.objects.filter(tags__in=[t1, t2]).filter(tags=t3)
[<Item: two>]

Bug #2080, #3592
>>> Author.objects.filter(item__name='one') | Author.objects.filter(name='a3')
[<Author: a1>, <Author: a3>]
>>> Author.objects.filter(Q(item__name='one') | Q(name='a3'))
[<Author: a1>, <Author: a3>]
>>> Author.objects.filter(Q(name='a3') | Q(item__name='one'))
[<Author: a1>, <Author: a3>]
>>> Author.objects.filter(Q(item__name='three') | Q(report__name='r3'))
[<Author: a2>]

Bug #4289
A slight variation on the above theme: restricting the choices by the lookup
constraints.
>>> Number.objects.filter(num__lt=4)
[]
>>> Number.objects.filter(num__gt=8, num__lt=12)
[]
>>> Number.objects.filter(num__gt=8, num__lt=13)
[<Number: 12>]
>>> Number.objects.filter(Q(num__lt=4) | Q(num__gt=8, num__lt=12))
[]
>>> Number.objects.filter(Q(num__gt=8, num__lt=12) | Q(num__lt=4))
[]
>>> Number.objects.filter(Q(num__gt=8) & Q(num__lt=12) | Q(num__lt=4))
[]
>>> Number.objects.filter(Q(num__gt=7) & Q(num__lt=12) | Q(num__lt=4))
[<Number: 8>]

Bug #6074
Merging two empty result sets shouldn't leave a queryset with no constraints
(which would match everything).
>>> Author.objects.filter(Q(id__in=[]))
[]
>>> Author.objects.filter(Q(id__in=[])|Q(id__in=[]))
[]

Bug #1878, #2939
>>> Item.objects.values('creator').distinct().count()
3

# Create something with a duplicate 'name' so that we can test multi-column
# cases (which require some tricky SQL transformations under the covers).
>>> xx = Item(name='four', created=time1, creator=a2, note=n1)
>>> xx.save()
>>> Item.objects.exclude(name='two').values('creator', 'name').distinct().count()
4
>>> Item.objects.exclude(name='two').extra(select={'foo': '%s'}, select_params=(1,)).values('creator', 'name', 'foo').distinct().count()
4
>>> Item.objects.exclude(name='two').extra(select={'foo': '%s'}, select_params=(1,)).values('creator', 'name').distinct().count()
4
>>> xx.delete()

Bug #2253
>>> q1 = Item.objects.order_by('name')
>>> q2 = Item.objects.filter(id=i1.id)
>>> q1
[<Item: four>, <Item: one>, <Item: three>, <Item: two>]
>>> q2
[<Item: one>]
>>> (q1 | q2).order_by('name')
[<Item: four>, <Item: one>, <Item: three>, <Item: two>]
>>> (q1 & q2).order_by('name')
[<Item: one>]

# FIXME: This is difficult to fix and very much an edge case, so punt for now.
# # This is related to the order_by() tests, below, but the old bug exhibited
# # itself here (q2 was pulling too many tables into the combined query with the
# # new ordering, but only because we have evaluated q2 already).
# >>> len((q1 & q2).order_by('name').query.tables)
# 1

>>> q1 = Item.objects.filter(tags=t1)
>>> q2 = Item.objects.filter(note=n3, tags=t2)
>>> q3 = Item.objects.filter(creator=a4)
>>> ((q1 & q2) | q3).order_by('name')
[<Item: four>, <Item: one>]

Bugs #4088, #4306
>>> Report.objects.filter(creator=1001)
[<Report: r1>]
>>> Report.objects.filter(creator__num=1001)
[<Report: r1>]
>>> Report.objects.filter(creator__id=1001)
[]
>>> Report.objects.filter(creator__id=a1.id)
[<Report: r1>]
>>> Report.objects.filter(creator__name='a1')
[<Report: r1>]

Bug #4510
>>> Author.objects.filter(report__name='r1')
[<Author: a1>]

Bug #5324, #6704
>>> Item.objects.filter(tags__name='t4')
[<Item: four>]
>>> Item.objects.exclude(tags__name='t4').order_by('name').distinct()
[<Item: one>, <Item: three>, <Item: two>]
>>> Item.objects.exclude(tags__name='t4').order_by('name').distinct().reverse()
[<Item: two>, <Item: three>, <Item: one>]
>>> Author.objects.exclude(item__name='one').distinct().order_by('name')
[<Author: a2>, <Author: a3>, <Author: a4>]


# Excluding across a m2m relation when there is more than one related object
# associated was problematic.
>>> Item.objects.exclude(tags__name='t1').order_by('name')
[<Item: four>, <Item: three>]
>>> Item.objects.exclude(tags__name='t1').exclude(tags__name='t4')
[<Item: three>]

# Excluding from a relation that cannot be NULL should not use outer joins.
>>> query = Item.objects.exclude(creator__in=[a1, a2]).query
>>> query.LOUTER not in [x[2] for x in query.alias_map.values()]
True

Similarly, when one of the joins cannot possibly, ever, involve NULL values (Author -> ExtraInfo, in the following), it should never be promoted to a left outer join. So hte following query should only involve one "left outer" join (Author -> Item is 0-to-many).
>>> qs = Author.objects.filter(id=a1.id).filter(Q(extra__note=n1)|Q(item__note=n3))
>>> len([x[2] for x in qs.query.alias_map.values() if x[2] == query.LOUTER])
1

The previous changes shouldn't affect nullable foreign key joins.
>>> Tag.objects.filter(parent__isnull=True).order_by('name')
[<Tag: t1>]
>>> Tag.objects.exclude(parent__isnull=True).order_by('name')
[<Tag: t2>, <Tag: t3>, <Tag: t4>, <Tag: t5>]
>>> Tag.objects.exclude(Q(parent__name='t1') | Q(parent__isnull=True)).order_by('name')
[<Tag: t4>, <Tag: t5>]
>>> Tag.objects.exclude(Q(parent__isnull=True) | Q(parent__name='t1')).order_by('name')
[<Tag: t4>, <Tag: t5>]
>>> Tag.objects.exclude(Q(parent__parent__isnull=True)).order_by('name')
[<Tag: t4>, <Tag: t5>]
>>> Tag.objects.filter(~Q(parent__parent__isnull=True)).order_by('name')
[<Tag: t4>, <Tag: t5>]

Bug #2091
>>> t = Tag.objects.get(name='t4')
>>> Item.objects.filter(tags__in=[t])
[<Item: four>]

Combining querysets built on different models should behave in a well-defined
fashion. We raise an error.
>>> Author.objects.all() & Tag.objects.all()
Traceback (most recent call last):
...
AssertionError: Cannot combine queries on two different base models.
>>> Author.objects.all() | Tag.objects.all()
Traceback (most recent call last):
...
AssertionError: Cannot combine queries on two different base models.

Bug #3141
>>> Author.objects.extra(select={'foo': '1'}).count()
4
>>> Author.objects.extra(select={'foo': '%s'}, select_params=(1,)).count()
4

Bug #2400
>>> Author.objects.filter(item__isnull=True)
[<Author: a3>]
>>> Tag.objects.filter(item__isnull=True)
[<Tag: t5>]

Bug #2496
>>> Item.objects.extra(tables=['queries_author']).select_related().order_by('name')[:1]
[<Item: four>]

Bug #2076
# Ordering on related tables should be possible, even if the table is not
# otherwise involved.
>>> Item.objects.order_by('note__note', 'name')
[<Item: two>, <Item: four>, <Item: one>, <Item: three>]

# Ordering on a related field should use the remote model's default ordering as
# a final step.
>>> Author.objects.order_by('extra', '-name')
[<Author: a2>, <Author: a1>, <Author: a4>, <Author: a3>]

# Using remote model default ordering can span multiple models (in this case,
# Cover is ordered by Item's default, which uses Note's default).
>>> Cover.objects.all()
[<Cover: first>, <Cover: second>]

# If you're not careful, it's possible to introduce infinite loops via default
# ordering on foreign keys in a cycle. We detect that.
>>> LoopX.objects.all()
Traceback (most recent call last):
...
FieldError: Infinite loop caused by ordering.

>>> LoopZ.objects.all()
Traceback (most recent call last):
...
FieldError: Infinite loop caused by ordering.

# ... but you can still order in a non-recursive fashion amongst linked fields
# (the previous test failed because the default ordering was recursive).
>>> LoopX.objects.all().order_by('y__x__y__x__id')
[]

# If the remote model does not have a default ordering, we order by its 'id'
# field.
>>> Item.objects.order_by('creator', 'name')
[<Item: one>, <Item: three>, <Item: two>, <Item: four>]

# Cross model ordering is possible in Meta, too.
>>> Ranking.objects.all()
[<Ranking: 3: a1>, <Ranking: 2: a2>, <Ranking: 1: a3>]
>>> Ranking.objects.all().order_by('rank')
[<Ranking: 1: a3>, <Ranking: 2: a2>, <Ranking: 3: a1>]

# Ordering by a many-valued attribute (e.g. a many-to-many or reverse
# ForeignKey) is legal, but the results might not make sense. That isn't
# Django's problem. Garbage in, garbage out.
>>> Item.objects.all().order_by('tags', 'id')
[<Item: one>, <Item: two>, <Item: one>, <Item: two>, <Item: four>]

# If we replace the default ordering, Django adjusts the required tables
# automatically. Item normally requires a join with Note to do the default
# ordering, but that isn't needed here.
>>> qs = Item.objects.order_by('name')
>>> qs
[<Item: four>, <Item: one>, <Item: three>, <Item: two>]
>>> len(qs.query.tables)
1

# Ordering of extra() pieces is possible, too and you can mix extra fields and
# model fields in the ordering.
>>> Ranking.objects.extra(tables=['django_site'], order_by=['-django_site.id', 'rank'])
[<Ranking: 1: a3>, <Ranking: 2: a2>, <Ranking: 3: a1>]

>>> qs = Ranking.objects.extra(select={'good': 'case when rank > 2 then 1 else 0 end'})
>>> [o.good for o in qs.extra(order_by=('-good',))] == [True, False, False]
True
>>> qs.extra(order_by=('-good', 'id'))
[<Ranking: 3: a1>, <Ranking: 2: a2>, <Ranking: 1: a3>]

# Despite having some extra aliases in the query, we can still omit them in a
# values() query.
>>> qs.values('id', 'rank').order_by('id')
[{'id': 1, 'rank': 2}, {'id': 2, 'rank': 1}, {'id': 3, 'rank': 3}]

Bugs #2874, #3002
>>> qs = Item.objects.select_related().order_by('note__note', 'name')
>>> list(qs)
[<Item: two>, <Item: four>, <Item: one>, <Item: three>]

# This is also a good select_related() test because there are multiple Note
# entries in the SQL. The two Note items should be different.
>>> qs[0].note, qs[0].creator.extra.note
(<Note: n2>, <Note: n1>)

Bug #3037
>>> Item.objects.filter(Q(creator__name='a3', name='two')|Q(creator__name='a4', name='four'))
[<Item: four>]

Bug #5321, #7070

Ordering columns must be included in the output columns. Note that this means
results that might otherwise be distinct are not (if there are multiple values
in the ordering cols), as in this example. This isn't a bug; it's a warning to
be careful with the selection of ordering columns.

>>> Note.objects.values('misc').distinct().order_by('note', '-misc')
[{'misc': u'foo'}, {'misc': u'bar'}, {'misc': u'foo'}]

Bug #4358
If you don't pass any fields to values(), relation fields are returned as
"foo_id" keys, not "foo". For consistency, you should be able to pass "foo_id"
in the fields list and have it work, too. We actually allow both "foo" and
"foo_id".

# The *_id version is returned by default.
>>> 'note_id' in ExtraInfo.objects.values()[0]
True

# You can also pass it in explicitly.
>>> ExtraInfo.objects.values('note_id')
[{'note_id': 1}, {'note_id': 2}]

# ...or use the field name.
>>> ExtraInfo.objects.values('note')
[{'note': 1}, {'note': 2}]

Bug #5261
>>> Note.objects.exclude(Q())
[<Note: n1>, <Note: n2>, <Note: n3>]

Bug #3045, #3288
Once upon a time, select_related() with circular relations would loop
infinitely if you forgot to specify "depth". Now we set an arbitrary default
upper bound.
>>> X.objects.all()
[]
>>> X.objects.select_related()
[]

Bug #3739
The all() method on querysets returns a copy of the queryset.
>>> q1 = Item.objects.order_by('name')
>>> id(q1) == id(q1.all())
False

Bug #2902
Parameters can be given to extra_select, *if* you use a SortedDict.

(First we need to know which order the keys fall in "naturally" on your system,
so we can put things in the wrong way around from normal. A normal dict would
thus fail.)
>>> from django.utils.datastructures import SortedDict
>>> s = [('a', '%s'), ('b', '%s')]
>>> params = ['one', 'two']
>>> if {'a': 1, 'b': 2}.keys() == ['a', 'b']:
...     s.reverse()
...     params.reverse()

# This slightly odd comparison works aorund the fact that PostgreSQL will
# return 'one' and 'two' as strings, not Unicode objects. It's a side-effect of
# using constants here and not a real concern.
>>> d = Item.objects.extra(select=SortedDict(s), select_params=params).values('a', 'b')[0]
>>> d == {'a': u'one', 'b': u'two'}
True

# Order by the number of tags attached to an item.
>>> l = Item.objects.extra(select={'count': 'select count(*) from queries_item_tags where queries_item_tags.item_id = queries_item.id'}).order_by('-count')
>>> [o.count for o in l]
[2, 2, 1, 0]

Bug #6154
Multiple filter statements are joined using "AND" all the time.

>>> Author.objects.filter(id=a1.id).filter(Q(extra__note=n1)|Q(item__note=n3))
[<Author: a1>]
>>> Author.objects.filter(Q(extra__note=n1)|Q(item__note=n3)).filter(id=a1.id)
[<Author: a1>]

Bug #6981
>>> Tag.objects.select_related('parent').order_by('name')
[<Tag: t1>, <Tag: t2>, <Tag: t3>, <Tag: t4>, <Tag: t5>]

Bug #6180, #6203 -- dates with limits and/or counts
>>> Item.objects.count()
4
>>> Item.objects.dates('created', 'month').count()
1
>>> Item.objects.dates('created', 'day').count()
2
>>> len(Item.objects.dates('created', 'day'))
2
>>> Item.objects.dates('created', 'day')[0]
datetime.datetime(2007, 12, 19, 0, 0)

Bug #7087 -- dates with extra select columns
>>> Item.objects.dates('created', 'day').extra(select={'a': 1})
[datetime.datetime(2007, 12, 19, 0, 0), datetime.datetime(2007, 12, 20, 0, 0)]

Test that parallel iterators work.

>>> qs = Tag.objects.all()
>>> i1, i2 = iter(qs), iter(qs)
>>> i1.next(), i1.next()
(<Tag: t1>, <Tag: t2>)
>>> i2.next(), i2.next(), i2.next()
(<Tag: t1>, <Tag: t2>, <Tag: t3>)
>>> i1.next()
<Tag: t3>

>>> qs = X.objects.all()
>>> bool(qs)
False
>>> bool(qs)
False

We can do slicing beyond what is currently in the result cache, too.

## FIXME!! This next test causes really weird PostgreSQL behaviour, but it's
## only apparent much later when the full test suite runs. I don't understand
## what's going on here yet.
##
## # We need to mess with the implemenation internals a bit here to decrease the
## # cache fill size so that we don't read all the results at once.
## >>> from django.db.models import query
## >>> query.ITER_CHUNK_SIZE = 2
## >>> qs = Tag.objects.all()
##
## # Fill the cache with the first chunk.
## >>> bool(qs)
## True
## >>> len(qs._result_cache)
## 2
##
## # Query beyond the end of the cache and check that it is filled out as required.
## >>> qs[4]
## <Tag: t5>
## >>> len(qs._result_cache)
## 5
##
## # But querying beyond the end of the result set will fail.
## >>> qs[100]
## Traceback (most recent call last):
## ...
## IndexError: ...

Bug #7045 -- extra tables used to crash SQL construction on the second use.
>>> qs = Ranking.objects.extra(tables=['django_site'])
>>> s = qs.query.as_sql()
>>> s = qs.query.as_sql()   # test passes if this doesn't raise an exception.

Bug #7098 -- Make sure semi-deprecated ordering by related models syntax still
works.
>>> Item.objects.values('note__note').order_by('queries_note.note', 'id')
[{'note__note': u'n2'}, {'note__note': u'n3'}, {'note__note': u'n3'}, {'note__note': u'n3'}]

Bug #7096 -- Make sure exclude() with multiple conditions continues to work.
>>> Tag.objects.filter(parent=t1, name='t3').order_by('name')
[<Tag: t3>]
>>> Tag.objects.exclude(parent=t1, name='t3').order_by('name')
[<Tag: t1>, <Tag: t2>, <Tag: t4>, <Tag: t5>]
>>> Item.objects.exclude(tags__name='t1', name='one').order_by('name').distinct()
[<Item: four>, <Item: three>, <Item: two>]
>>> Item.objects.filter(name__in=['three', 'four']).exclude(tags__name='t1').order_by('name')
[<Item: four>, <Item: three>]

More twisted cases, involving nested negations.
>>> Item.objects.exclude(~Q(tags__name='t1', name='one'))
[<Item: one>]
>>> Item.objects.filter(~Q(tags__name='t1', name='one'), name='two')
[<Item: two>]
>>> Item.objects.exclude(~Q(tags__name='t1', name='one'), name='two')
[<Item: four>, <Item: one>, <Item: three>]

Bug #7095
Updates that are filtered on the model being updated are somewhat tricky to get
in MySQL. This exercises that case.
>>> mm = ManagedModel.objects.create(data='mm1', tag=t1, public=True)
>>> ManagedModel.objects.update(data='mm')

"""}

