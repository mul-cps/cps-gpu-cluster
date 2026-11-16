# Installed RTC held-socket fixture guidance

Read-only inspection of immutable notebook image `4a03fe381c6f32f8e056ac05aad27abc64defa2f63128c53511a24d37fb5c194`; jupyter-server-ydoc 2.4.2, pycrdt 0.13.1. No live requests or tokens were used by this reviewer. The workspace agent owns the separately authorized Source QA fixture.

For existing notebook `registry-qa-session.ipynb`, relative to the actual singleuser server base URL:

1. Authenticated **PUT** `/api/collaboration/session/registry-qa-session.ipynb`, JSON `{"format":"json","type":"notebook"}`, with the authorized QA user's token header. Expect HTTP 200 for already indexed files or 201 for a newly indexed existing file. Response contains `format`, `type`, `fileId`, `sessionId`.
2. Open authenticated WebSocket `/api/collaboration/room/json:notebook:{fileId}?sessionId={sessionId}` on the same server base, using ws/wss consistent with HTTP/HTTPS. Use the returned IDs; preserve literal `:` separators in the room path. This installed parser splits the encoded final path segment on literal colons, so percent-encoding the entire room name would select the wrong kind of room. Encode individual returned components if needed, not the separators.
3. No WebSocket subprotocol is required by this RTC handler. Await an initial binary server sync frame with a bounded timeout, record that the connection remains open, then keep the receiving task alive through the authoritative remove-member call. No document edit or hand-built Yjs update is necessary to witness an authenticated open RTC transport. The actual server GET validates access and `open` loads/initializes the document room.
4. Use the returned `sessionId`; a mismatching/stale session can itself trigger close code 1003, which must not be mistaken for membership revocation. The connection must remain open until the remove-member operation starts.
5. Record server-triggered closure/EOF and timestamps after the Source API's lifecycle action. Do not close the client first, and do not conflate a local timeout/cancellation with peer closure. Confirm the kernel socket similarly closes and subsequent requests/reconnects for the removed member fail, including after permitted peer restart.

Source references in `installed-source/jupyter_server_ydoc/`:

- `app.py:152`: RTC room route; `:163`: document session route.
- `handlers.py:495–549`: PUT body, file indexing and response.
- `handlers.py:229`: authenticated/authorized WebSocket GET.
- `handlers.py:238–285`: room serve/start and returned-session compatibility check.
- `handlers.py:94`: room ID read from final encoded path segment; utility `decode_file_path` splits `format:type:fileId` on literal `:`.

If a full protocol exchange is desired, installed `pycrdt.create_sync_message(pycrdt.Doc())` produces the standard initial binary sync request. The old name `pycrdt.websocket.WebsocketProvider` is **not** exported by this image; the public provider class is `pycrdt.Provider(doc, channel)`. The simpler held-socket test above avoids introducing an unnecessary adapter or document mutation.
