Version 0.4.2
-------------

(bugfix release, released on August 25st, 2014)

- Actions with no accepts or returns parameters broke.
- Move API object storage (``cosmos``) out of thread-locals. This broke Cosmic
  in multi-threaded environments.
- Let ``API.run`` accept ``debug`` parameter.
- Changed ``Server.unhandled_exception_hook`` behavior:
   - Pass request object as second parameter.
   - Don't call it when ``Server.debug`` is true.
- New thread-local API:
   - ``SafeGlobal`` gone in favor of ``SwappableDict` and ``ThreadLocalDict``
   - Swapping API instead of stack API.
   - ``thread_local`` context manager takes care of cleaning up.

Version 0.4.1
-------------

(bugfix release, released on August 21st, 2014)

- Fixed ``cosmic.client.ClientLoggingMixin`` so that the ``log`` value is JSON
  serializable and the headers are represented consistently by lists of tuples.
- Added CHANGES file
- Improved ``long_description`` for PyPI
