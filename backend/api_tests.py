# Compatibility entrypoint for CI systems that discover root-level tests.
from accounts.tests import *
from products.tests import *
from auctions.tests import *
from bidding.tests import *
from payments.tests import *
