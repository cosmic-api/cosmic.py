Version 0.5.3
-------------

(bugfix release, released on November 24th, 2014)

- Documentation: note that Cosmic uses an out-of-date version of Teleport.
- Make it possible to install Teleport side-by-side by using a packaged copy.

Version 0.5.2
-------------

(bugfix release, released on September 14th, 2014)

- Fix bug in link representation, foreign links were represented as URLs of
  the same model.
- Avoid reraising exceptions in http module to preserve original stack traces.

Version 0.5.1
-------------

(bugfix release, released on September 12th, 2014)

- Wrote documentation for the ``cosmic.globals`` module.
- Implemented ``cosmic.globals.thread_local_middleware``.
- Now the server doesn't force the creation of a thread-local on every request,
  it checks if one exists already. This allows using the middleware explicitly.

Version 0.5.0
-------------

Released on September 10th, 2014

- ``cosmic.Link`` type's JSON form is a string containing a URL, the "href"
  part was moved into ``cosmic.BaseRepresentation``. This makes the Link type
  friendlier for actions.

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
   - ``SafeGlobal`` gone in favor of ``SwappableDict`` and ``ThreadLocalDict``
   - Swapping API instead of stack API.
   - ``thread_local`` context manager takes care of cleaning up.

Version 0.4.1
-------------

(bugfix release, released on August 21st, 2014)

- Fixed ``cosmic.client.ClientLoggingMixin`` so that the ``log`` value is JSON
  serializable and the headers are represented consistently by lists of tuples.
- Added CHANGES file
- Improved ``long_description`` for PyPI
