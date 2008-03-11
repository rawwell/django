"""
Query subclasses which provide extra functionality beyond simple data retrieval.
"""

from django.contrib.contenttypes import generic
from django.core.exceptions import FieldError
from django.db.models.sql.constants import *
from django.db.models.sql.datastructures import RawValue, Date
from django.db.models.sql.query import Query
from django.db.models.sql.where import AND

__all__ = ['DeleteQuery', 'UpdateQuery', 'InsertQuery', 'DateQuery',
        'CountQuery']

class DeleteQuery(Query):
    """
    Delete queries are done through this class, since they are more constrained
    than general queries.
    """
    def as_sql(self):
        """
        Creates the SQL for this query. Returns the SQL string and list of
        parameters.
        """
        assert len(self.tables) == 1, \
                "Can only delete from one table at a time."
        result = ['DELETE FROM %s' % self.tables[0]]
        where, params = self.where.as_sql()
        result.append('WHERE %s' % where)
        return ' '.join(result), tuple(params)

    def do_query(self, table, where):
        self.tables = [table]
        self.where = where
        self.execute_sql(None)

    def delete_batch_related(self, pk_list):
        """
        Set up and execute delete queries for all the objects related to the
        primary key values in pk_list. To delete the objects themselves, use
        the delete_batch() method.

        More than one physical query may be executed if there are a
        lot of values in pk_list.
        """
        cls = self.model
        for related in cls._meta.get_all_related_many_to_many_objects():
            if not isinstance(related.field, generic.GenericRelation):
                for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
                    where = self.where_class()
                    where.add((None, related.field.m2m_reverse_name(),
                            related.field, 'in',
                            pk_list[offset : offset+GET_ITERATOR_CHUNK_SIZE]),
                            AND)
                    self.do_query(related.field.m2m_db_table(), where)

        for f in cls._meta.many_to_many:
            w1 = self.where_class()
            if isinstance(f, generic.GenericRelation):
                from django.contrib.contenttypes.models import ContentType
                field = f.rel.to._meta.get_field(f.content_type_field_name)
                w1.add((None, field.column, field, 'exact',
                        ContentType.objects.get_for_model(cls).id), AND)
            for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
                where = self.where_class()
                where.add((None, f.m2m_column_name(), f, 'in',
                        pk_list[offset : offset + GET_ITERATOR_CHUNK_SIZE]),
                        AND)
                if w1:
                    where.add(w1, AND)
                self.do_query(f.m2m_db_table(), where)

    def delete_batch(self, pk_list):
        """
        Set up and execute delete queries for all the objects in pk_list. This
        should be called after delete_batch_related(), if necessary.

        More than one physical query may be executed if there are a
        lot of values in pk_list.
        """
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            where = self.where_class()
            field = self.model._meta.pk
            where.add((None, field.column, field, 'in',
                    pk_list[offset : offset + GET_ITERATOR_CHUNK_SIZE]), AND)
            self.do_query(self.model._meta.db_table, where)

class UpdateQuery(Query):
    """
    Represents an "update" SQL query.
    """
    def __init__(self, *args, **kwargs):
        super(UpdateQuery, self).__init__(*args, **kwargs)
        self._setup_query()

    def _setup_query(self):
        """
        Runs on initialisation and after cloning. Any attributes that would
        normally be set in __init__ should go in here, instead, so that they
        are also set up after a clone() call.
        """
        self.values = []
        self.related_ids = None
        if not hasattr(self, 'related_updates'):
            self.related_updates = {}

    def clone(self, klass=None, **kwargs):
        return super(UpdateQuery, self).clone(klass,
                related_updates=self.related_updates.copy, **kwargs)

    def execute_sql(self, result_type=None):
        super(UpdateQuery, self).execute_sql(result_type)
        for query in self.get_related_updates():
            query.execute_sql(result_type)

    def as_sql(self):
        """
        Creates the SQL for this query. Returns the SQL string and list of
        parameters.
        """
        self.pre_sql_setup()
        if not self.values:
            return '', ()
        table = self.tables[0]
        qn = self.quote_name_unless_alias
        result = ['UPDATE %s' % qn(table)]
        result.append('SET')
        values, update_params = [], []
        for name, val in self.values:
            if val is not None:
                values.append('%s = %%s' % qn(name))
                update_params.append(val)
            else:
                values.append('%s = NULL' % qn(name))
        result.append(', '.join(values))
        where, params = self.where.as_sql()
        if where:
            result.append('WHERE %s' % where)
        return ' '.join(result), tuple(update_params + params)

    def pre_sql_setup(self):
        """
        If the update depends on results from other tables, we need to do some
        munging of the "where" conditions to match the format required for
        (portable) SQL updates. That is done here.

        Further, if we are going to be running multiple updates, we pull out
        the id values to update at this point so that they don't change as a
        result of the progressive updates.
        """
        self.select_related = False
        self.clear_ordering(True)
        super(UpdateQuery, self).pre_sql_setup()
        count = self.count_active_tables()
        if not self.related_updates and count == 1:
            return

        # We need to use a sub-select in the where clause to filter on things
        # from other tables.
        query = self.clone(klass=Query)
        alias = '%s0' % self.alias_prefix
        query.change_alias(query.tables[0], alias)
        self.add_local_columns([query.model._meta.pk.column])

        # Now we adjust the current query: reset the where clause and get rid
        # of all the tables we don't need (since they're in the sub-select).
        self.where = self.where_class()
        if self.related_updates:
            idents = []
            for rows in query.execute_sql(MULTI):
                idents.extend([r[0] for r in rows])
            self.add_filter(('pk__in', idents))
            self.related_ids = idents
        else:
            self.add_filter(('pk__in', query))
        for alias in self.tables[1:]:
            self.alias_map[alias][ALIAS_REFCOUNT] = 0

    def clear_related(self, related_field, pk_list):
        """
        Set up and execute an update query that clears related entries for the
        keys in pk_list.

        This is used by the QuerySet.delete_objects() method.
        """
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            self.where = self.where_class()
            f = self.model._meta.pk
            self.where.add((None, f.column, f, 'in',
                    pk_list[offset : offset + GET_ITERATOR_CHUNK_SIZE]),
                    AND)
            self.values = [(related_field.column, None)]
            self.execute_sql(None)

    def add_update_values(self, values):
        from django.db.models.base import Model
        for name, val in values.items():
            field, model, direct, m2m = self.model._meta.get_field_by_name(name)
            if not direct or m2m:
                raise FieldError('Cannot update model field %r (only non-relations and foreign keys permitted).' % field)
            # FIXME: Some sort of db_prep_* is probably more appropriate here.
            if field.rel and isinstance(val, Model):
                val = val.pk
            if model:
                self.add_related_update(model, field.column, val)
            else:
                self.values.append((field.column, val))

    def add_related_update(self, model, column, value):
        """
        Adds (name, value) to an update query for an ancestor model.

        Updates are coalesced so that we only run one update query per ancestor.
        """
        try:
            self.related_updates[model].append((column, value))
        except KeyError:
            self.related_updates[model] = [(column, value)]

    def get_related_updates(self):
        """
        Returns a list of query objects: one for each update required to an
        ancestor model. Each query will have the same filtering conditions as
        the current query but will only update a single table.
        """
        if not self.related_updates:
            return []
        result = []
        for model, values in self.related_updates.items():
            query = UpdateQuery(model, self.connection)
            query.values = values
            if self.related_ids:
                query.add_filter(('pk__in', self.related_ids))
            result.append(query)
        return result

class InsertQuery(Query):
    def __init__(self, *args, **kwargs):
        super(InsertQuery, self).__init__(*args, **kwargs)
        self._setup_query()

    def _setup_query(self):
        """
        Run on initialisation and after cloning.
        """
        self.columns = []
        self.values = []

    def as_sql(self):
        self.select_related = False
        self.pre_sql_setup()
        qn = self.quote_name_unless_alias
        result = ['INSERT INTO %s' % qn(self.tables[0])]
        result.append('(%s)' % ', '.join([qn(c) for c in self.columns]))
        result.append('VALUES (')
        params = []
        first = True
        for value in self.values:
            prefix = not first and ', ' or ''
            if isinstance(value, RawValue):
                result.append('%s%s' % (prefix, value.value))
            else:
                result.append('%s%%s' % prefix)
                params.append(value)
            first = False
        result.append(')')
        return ' '.join(result), tuple(params)

    def execute_sql(self, return_id=False):
        cursor = super(InsertQuery, self).execute_sql(None)
        if return_id:
            return self.connection.ops.last_insert_id(cursor, self.tables[0],
                    self.model._meta.pk.column)

    def insert_values(self, insert_values, raw_values=False):
        """
        Set up the insert query from the 'insert_values' dictionary. The
        dictionary gives the model field names and their target values.

        If 'raw_values' is True, the values in the 'insert_values' dictionary
        are inserted directly into the query, rather than passed as SQL
        parameters. This provides a way to insert NULL and DEFAULT keywords
        into the query, for example.
        """
        func = lambda x: self.model._meta.get_field_by_name(x)[0].column
        # keys() and values() return items in the same order, providing the
        # dictionary hasn't changed between calls. So these lines work as
        # intended.
        for name in insert_values:
            if name == 'pk':
                name = self.model._meta.pk.name
            self.columns.append(func(name))
        if raw_values:
            self.values.extend([RawValue(v) for v in insert_values.values()])
        else:
            self.values.extend(insert_values.values())

class DateQuery(Query):
    """
    A DateQuery is a normal query, except that it specifically selects a single
    date field. This requires some special handling when converting the results
    back to Python objects, so we put it in a separate class.
    """
    def results_iter(self):
        """
        Returns an iterator over the results from executing this query.
        """
        resolve_columns = hasattr(self, 'resolve_columns')
        if resolve_columns:
            from django.db.models.fields import DateTimeField
            fields = [DateTimeField()]
        else:
            from django.db.backends.util import typecast_timestamp
            needs_string_cast = self.connection.features.needs_datetime_string_cast

        for rows in self.execute_sql(MULTI):
            for row in rows:
                date = row[0]
                if resolve_columns:
                    date = self.resolve_columns([date], fields)[0]
                elif needs_string_cast:
                    date = typecast_timestamp(str(date))
                yield date

    def add_date_select(self, column, lookup_type, order='ASC'):
        """
        Converts the query into a date extraction query.
        """
        alias = self.join((None, self.model._meta.db_table, None, None))
        select = Date((alias, column), lookup_type,
                self.connection.ops.date_trunc_sql)
        self.select = [select]
        self.distinct = True
        self.order_by = order == 'ASC' and [1] or [-1]

class CountQuery(Query):
    """
    A CountQuery knows how to take a normal query which would select over
    multiple distinct columns and turn it into SQL that can be used on a
    variety of backends (it requires a select in the FROM clause).
    """
    def get_from_clause(self):
        result, params = self._query.as_sql()
        return ['(%s) AS A1' % result], params

    def get_ordering(self):
        return ()
