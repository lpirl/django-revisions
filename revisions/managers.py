# encoding: utf-8

from datetime import datetime
from django.db import models
import inspect

class LatestManager(models.Manager):
    """ A manager that returns the latest revision of each bundle of content. """
    # use_for_related_fields makes sure this manager works
    # seamlessly with inline formsets
    use_for_related_fields = True
    
    @classmethod
    def show_latest(cls, qs):
        """
        to get the base table, rather than the joined one (should we need this later on):
        
        base = qs.query.model
        while isinstance(base._meta.pk, models.OneToOneField):
            base = base._meta.pk.rel.to
        table = base._meta.db_table
        """

        # this may or may not be the fastest way to get the last revision of every
        # piece of content, depending on how your database query optimizer works, 
        # but it sure as hell is the easiest way to do it in Django without resorting
        # to multiple queries or working entirely with raw SQL.
        
        table = qs.query.model._meta.db_table
        where = 'vid = (SELECT MAX(vid) FROM %(table)s as sub WHERE %(table)s.id = sub.id)' % {'table': table}
        return qs.extra(where=[where])
    
    def get_query_set(self):              
        # Django uses the default manager (which on versioned models is this one)
        # to determine what to do when it saves a model instance. Because older
        # revisions aren't included in the queryset for LatestManager, when trying
        # to update such an older revision, the ORM gets confused and tries to insert 
        # a new record, or, when you pass force_update=True, Django complains that it 
        # couldn't find the right row to update.
        #
        # Specifically, you either get an IntegrityError saying "PRIMARY KEY must be unique" 
        # or a DatabaseError saying "Forced update did not affect any rows."
        #
        # We solve this little issue by simply using the plain models.Manager queryset
        # when saving. Simple fix, but it does require some trickery with the inspect
        # module.
        #
        # revisions.tests.AppTests.test_update_old_revision_in_place tests whether this works.
        
        qs = super(LatestManager, self).get_query_set()
                
        if inspect.stack()[3][3] == 'save':
            return qs
        else:
            return LatestManager.show_latest(qs)

def trash_aware(cls):
    for manager in cls._meta.abstract_managers:
        manager[2].trash = manager[2].filter(_is_trash=True)
        manager[2].live = manager[2].filter(_is_trash=False)
    return cls