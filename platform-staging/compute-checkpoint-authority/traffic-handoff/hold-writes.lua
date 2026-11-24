local writer_map = Map.new("/handoff-config/writer.map", Map._str)
local hold_microseconds = 4700000

local function now_microseconds()
    local now = core.now()
    return now.sec * 1000000 + now.usec
end

core.register_action("wait_for_gateway_writer", {"http-req"}, function(txn)
    local deadline = now_microseconds() + hold_microseconds
    while true do
        local writer = writer_map:lookup("active")
        if writer == "incumbent" or writer == "candidate" then
            txn:set_var("txn.gateway_writer", writer)
            return
        end
        if writer ~= "hold" or now_microseconds() >= deadline then
            return
        end
        core.msleep(5)
    end
end)
