lazy val lib = project.in(file("lib"))
lazy val graph = project.in(file("graph")).dependsOn(lib)
lazy val facet = project.in(file("facet")).dependsOn(graph)
lazy val agent = project.in(file("agent")).dependsOn(graph)
