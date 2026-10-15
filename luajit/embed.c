/* embed.c — 把 LuaJIT 编进产物：内嵌 Lua 脚本 + 可调运行时函数(libimgproc 静态链入)
 *
 * 运行:
 *   ./OUT                # 跑内嵌脚本，argv 经 Lua 全局 arg 传入
 *   ./OUT script.lua ... # 跑指定 Lua 脚本
 */
#include <lua.h>
#include <lauxlib.h>
#include <lualib.h>
#include <stdio.h>
#include <string.h>

#if __has_include("embed_lua.h")
#include "embed_lua.h"
#define HAVE_EMBED 1
#endif

static void set_arg(lua_State* L, int argc, char** argv) {
    lua_newtable(L);
    for (int i = 0; i < argc; i++) { lua_pushstring(L, argv[i]); lua_rawseti(L, -2, i); }
    lua_setglobal(L, "arg");
}

static int ends_with(const char* s, const char* suf) {
    size_t ls = strlen(s), lf = strlen(suf);
    return lf <= ls && strcmp(s + ls - lf, suf) == 0;
}

int main(int argc, char** argv) {
    lua_State* L = luaL_newstate();
    luaL_openlibs(L);
    set_arg(L, argc, argv);

    int rc;
    if (argc > 1 && ends_with(argv[1], ".lua")) {
        rc = luaL_loadfile(L, argv[1]);
        if (rc == LUA_OK) rc = lua_pcall(L, 0, 0, 0);
    } else {
#ifdef HAVE_EMBED
        rc = luaL_loadbuffer(L, (const char*)EMBED_LUA_SRC, EMBED_LUA_SRC_len, "app");
        if (rc == LUA_OK) rc = lua_pcall(L, 0, 0, 0);
#else
        fprintf(stderr, "usage: %s [script.lua | IN OUT]\n", argv[0]);
        rc = LUA_ERRFILE;
#endif
    }
    if (rc != LUA_OK) { fprintf(stderr, "lua error: %s\n", lua_tostring(L, -1)); return 1; }
    lua_close(L);
    return 0;
}
