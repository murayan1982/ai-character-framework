import asyncio
import os
import pyvts

from config.settings import (
    VTS_TOKEN_PATH,
    VTS_EMOTION_ALIAS,
    DEFAULT_EMOTION,
    VTS_DEBUG,
)


class VTSClient:
    def __init__(self):
        # Path to authentication token file
        self.token_path = VTS_TOKEN_PATH

        # Plugin information for VTube Studio API
        self.plugin_info = {
            "plugin_name": "AI Voice Bot Framework",
            "developer": "murayan",
            "authentication_token_path": self.token_path,
        }

        # Initialize client
        self.vts = pyvts.vts(plugin_info=self.plugin_info)

        # Connection state
        self.is_connected = False

        # Hotkey cache
        self.hotkey_cache = {}

        # Mutex for API calls
        self.lock = asyncio.Lock()

    def _debug(self, message: str) -> None:
        # Print debug logs only when enabled
        if VTS_DEBUG:
            print(message)

    async def connect(self):
        try:
            # Connect websocket
            await self.vts.connect()
            self._debug("[VTS] Websocket connected.")

            # Ensure token directory exists
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)

            # Load stored token if available
            if os.path.exists(self.token_path) and os.path.getsize(self.token_path) > 0:
                try:
                    await self.vts.read_token()
                    self._debug("[VTS] Stored token loaded.")
                except Exception as e:
                    print(f"[VTS] Failed to read token: {e}")

            self._debug("[VTS] Starting authentication flow...")

            authenticated = await self._try_authenticate_with_current_token()

            # Reissue token if current token is invalid
            if not authenticated:
                self._debug("[VTS] Token invalid or missing. Requesting new token...")

                if os.path.exists(self.token_path):
                    try:
                        os.remove(self.token_path)
                        self._debug("[VTS] Old token file removed.")
                    except Exception as e:
                        print(f"[VTS] Failed to remove token file: {e}")

                token_ok = await self._request_new_token()
                if not token_ok:
                    self.is_connected = False
                    return False

                authenticated = await self._try_authenticate_with_current_token()

            if not authenticated:
                print("[VTS Error] Authentication failed.")
                self.is_connected = False
                return False

            self.is_connected = True
            self._debug("[VTS] Authenticated.")
            await self._update_hotkey_cache()
            return True

        except Exception as e:
            self.is_connected = False
            print(f"[VTS Error] Connection failed: {e}")
            return False

    async def _try_authenticate_with_current_token(self) -> bool:
        try:
            if not getattr(self.vts, "authentic_token", None):
                self._debug("[VTS] No stored token available.")
                return False

            # Build auth request with current token
            request = self.vts.vts_request.authentication(self.vts.authentic_token)

            response = await self.vts.request(request)
            self._debug(f"[VTS] Auth response: {response}")
            return self._extract_authenticated(response)

        except Exception as e:
            print(f"[VTS] Auth request failed: {e}")
            return False

    async def _request_new_token(self) -> bool:
        try:
            # Build token request
            request = self.vts.vts_request.authentication_token()

            response = await self.vts.request(request)
            self._debug(f"[VTS] Token response: {response}")

            token = response.get("data", {}).get("authenticationToken")
            if not token:
                print("[VTS Error] No authenticationToken in response.")
                return False

            self.vts.authentic_token = token
            await self.vts.write_token()
            self._debug("[VTS] New token saved.")
            return True

        except Exception as e:
            print(f"[VTS Error] Token request failed: {e}")
            return False

    def _extract_authenticated(self, response) -> bool:
        # Accept both nested and flat response formats
        if not isinstance(response, dict):
            return False

        data = response.get("data")
        if isinstance(data, dict) and "authenticated" in data:
            return bool(data["authenticated"])

        if "authenticated" in response:
            return bool(response["authenticated"])

        return False

    async def _update_hotkey_cache(self):
        if not self.is_connected:
            return

        try:
            async with self.lock:
                response = await self.vts.request(
                    self.vts.vts_request.requestHotKeyList()
                )

                hotkeys = response.get("data", {}).get("availableHotkeys", [])
                self.hotkey_cache = {}

                for hk in hotkeys:
                    name = hk.get("name")
                    file_name = hk.get("file")
                    hotkey_id = hk.get("hotkeyID")

                    if name and hotkey_id:
                        self.hotkey_cache[name] = hotkey_id
                        self.hotkey_cache[name.lower()] = hotkey_id

                    if file_name and hotkey_id:
                        self.hotkey_cache[file_name] = hotkey_id
                        self.hotkey_cache[file_name.lower()] = hotkey_id

                self._debug(f"[VTS] Cached {len(self.hotkey_cache)} hotkeys.")
                self._debug(f"[VTS] Hotkey names: {sorted(self.hotkey_cache.keys())}")

        except Exception as e:
            print(f"[VTS Error] Hotkey cache failed: {e}")

    async def change_expression(self, emotion: str):
        if not self.is_connected:
            return

        # Normalize emotion name
        normalized = emotion.strip().lower()
        original = normalized

        # Apply alias with fallback
        normalized = VTS_EMOTION_ALIAS.get(normalized, DEFAULT_EMOTION)

        if original != normalized:
            self._debug(f"[VTS] Emotion mapped: {original} -> {normalized}")

        hotkey_id = self.hotkey_cache.get(normalized)
        if not hotkey_id:
            self._debug(f"[VTS] No hotkey for emotion: {emotion} -> {normalized}")
            return

        try:
            async with self.lock:
                request = self.vts.vts_request.requestTriggerHotKey(hotkey_id)
                await self.vts.request(request)

        except Exception as e:
            self.is_connected = False
            print(f"[VTS Error] Send failed ({emotion}): {e}")

    async def reconnect(self):
        self.is_connected = False
        try:
            await self.vts.close()
        except Exception:
            pass
        await self.connect()
        
    async def close(self):
        self.is_connected = False

        if self.vts is None:
            return

        try:
            await self.vts.close()
            self.vts = None
        except Exception as e:
            print(f"[VTS Error] Close failed: {e}")