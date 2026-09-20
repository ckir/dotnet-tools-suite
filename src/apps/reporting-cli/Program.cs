// Copyright (c) 2026 Hellen
// Licensed under the PolyForm Noncommercial License 1.0.0

using System;
using System.CommandLine;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

var services = new ServiceCollection()
    .AddLogging(builder => builder.AddConsole())
    .BuildServiceProvider();

var logger = services.GetRequiredService<ILoggerFactory>().CreateLogger("reporting-cli");

var root = new RootCommand("reporting-cli root command");

root.SetAction(_ =>
{
    logger.LogInformation("reporting-cli is running.");
    Console.WriteLine("reporting-cli executed.");
});

return await root.Parse(args).InvokeAsync();
