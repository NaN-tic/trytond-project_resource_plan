# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .resource import *
from .work import *


def register():
    Pool.register(
        Work,
        ProjectResourcePlanStart,
        ProjectResourcePlanTasks,
        PredecessorSuccessor,
        Allocation,
        ResourceBooking,
        module='project_resource_plan', type_='model')
    Pool.register(
        ProjectResourcePlan,
        module='project_resource_plan', type_='wizard')
