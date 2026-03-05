class PaymentServiceError(Exception):
    pass


class OrderNotFoundError(PaymentServiceError):
    pass


class PaymentNotFoundError(PaymentServiceError):
    pass


class OrderAlreadyPaidError(PaymentServiceError):
    pass


class PaymentAmountExceededError(PaymentServiceError):
    pass


class InvalidPaymentTypeError(PaymentServiceError):
    pass


class BankAPIError(PaymentServiceError):
    pass


class BankPaymentNotFoundError(BankAPIError):
    pass
