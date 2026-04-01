sed -i '' -e '/_start_agents()/i\
_build_mac_app() {\
    log_info "Building Mac App..."\
    if [[ -d "$ARMY_HOME/app" ]]; then\
        cd "$ARMY_HOME/app" && ./build.sh >/dev/null\
        if [[ -d "build/King AI.app" ]]; then\
            log_ok "App built. Installing to /Applications/"\
            killall "KingAI" 2>/dev/null || true\
            rm -rf "/Applications/King AI.app"\
            cp -R "build/King AI.app" "/Applications/"\
            log_ok "App installed to /Applications/King AI.app"\
        else\
            log_warn "App build failed."\
        fi\
        cd "$ARMY_HOME"\
    fi\
}\
\
' /Users/landonking/openclaw-army/deploy.sh
