from trytond.pool import Pool, PoolMeta

__all__ = ['ResourceBooking']
__metaclass__ = PoolMeta


class ResourceBooking:
    __name__ = 'resource.booking'

    @classmethod
    def confirm(cls, bookings):
        pool = Pool()
        Work = pool.get('project.work')
        super(ResourceBooking, cls).confirm(bookings)
        to_write = []
        for booking in bookings:
            work = booking.document
            if (work and isinstance(work, Work) and not work.assigned_employee
                    and booking.resource.employee):
                to_write.extend(([work], {
                            'assigned_employee': booking.resource.employee.id,
                            }))

        if to_write:
            Work.write(*to_write)
