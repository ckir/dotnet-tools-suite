// Copyright (c) 2026 Hellen
// Licensed under the PolyForm Noncommercial License 1.0.0

using System;
using System.CommandLine;
using Microsoft.Extensions.Logging;

var root = new RootCommand("tooling-cli");

root.SetAction(_ =>
{
    Console.WriteLine("tooling-cli is running.");
});

return await root.Parse(args).InvokeAsync();
